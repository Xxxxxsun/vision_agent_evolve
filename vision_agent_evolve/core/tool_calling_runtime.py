"""Function-calling VQA runtime with structured tools and persistent image session."""

from __future__ import annotations

import io
import json
import mimetypes
import os
import re
import shutil
import traceback
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image

from .skill_routing import ResolvedSkillContext, SkillResolver, resolve_skill_roots
from .types import AgentAction, AgentResult, AgentStep, Message, TaskCase
from .vlm_client import ModelSettings, VLMClient


SYSTEM_PROMPT = (
    "You are solving multimodal benchmark questions. "
    "Think through the visual evidence briefly before you commit to an answer. "
    "Use tools when they help you inspect evidence that is small, ambiguous, or easy to confuse. "
    "Use execute_python for calculations or verification. "
    "Use visual tools when local details, small text, or spatial evidence matters. "
    "The final line of your response must begin with 'Final answer:'."
)


@dataclass
class ToolCallingRuntimeConfig:
    """Configuration for the function-calling runtime."""

    max_iterations: int = 8
    model_settings: ModelSettings = field(
        default_factory=lambda: ModelSettings(temperature=0.0, max_tokens=1024)
    )
    enable_tools: bool = True
    work_dir: Path | None = None
    capability_root: Path | None = None
    static_skills_dir: Path | None = None
    use_skills: bool = True
    skill_mode: str = "function_calling_router"
    fixed_tool_names: list[str] = field(default_factory=list)


class LocalPythonExecutor:
    """Minimal persistent Python executor for numeric verification."""

    def __init__(self) -> None:
        self._globals: dict[str, Any] = {"__builtins__": __builtins__}

    def execute_code(self, code: str) -> dict[str, Any]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exec(code, self._globals, self._globals)
        except Exception as exc:
            details = stderr.getvalue()
            trace = traceback.format_exc()
            output = "\n".join(part for part in [stdout.getvalue(), details, trace] if part).strip()
            return {
                "output": output or str(exc),
                "error_type": type(exc).__name__,
            }
        output = "\n".join(part for part in [stdout.getvalue(), stderr.getvalue()] if part).strip()
        return {
            "output": output or "(No output)",
            "error_type": None,
        }


class RuntimeImageSession:
    """Persistent image registry for initial and derived images."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._images: dict[str, dict[str, Any]] = {}
        self._counter = 0

    def register_initial_images(self, image_refs: list[str]) -> list[str]:
        image_ids: list[str] = []
        for image_ref in image_refs:
            image_ids.append(self._register_initial_image(image_ref))
        return image_ids

    def list_images(self) -> list[dict[str, Any]]:
        return [dict(self._images[image_id]) for image_id in sorted(self._images.keys())]

    def get_image_info(self, image_id: str) -> dict[str, Any]:
        return dict(self._get_record(image_id))

    def crop_image(self, image_id: str, left: int, top: int, right: int, bottom: int) -> dict[str, Any]:
        record = self._get_record(image_id)
        with Image.open(record["path"]) as image:
            width, height = image.size
            crop_box = (
                max(0, int(left)),
                max(0, int(top)),
                min(width, int(right)),
                min(height, int(bottom)),
            )
            if crop_box[0] >= crop_box[2] or crop_box[1] >= crop_box[3]:
                raise ValueError("crop coordinates must define a non-empty region")
            cropped = image.crop(crop_box)
        new_record = self._save_generated(cropped, source_type="crop", source_image_id=image_id)
        return {
            **new_record,
            "crop_box": list(crop_box),
        }

    def zoom_image(
        self,
        image_id: str,
        factor: float,
        center_x: float = 0.5,
        center_y: float = 0.5,
    ) -> dict[str, Any]:
        if float(factor) <= 1.0:
            raise ValueError("zoom factor must be greater than 1.0")
        cx = max(0.0, min(1.0, float(center_x)))
        cy = max(0.0, min(1.0, float(center_y)))
        record = self._get_record(image_id)
        with Image.open(record["path"]) as image:
            width, height = image.size
            crop_width = max(1, int(round(width / float(factor))))
            crop_height = max(1, int(round(height / float(factor))))
            # Place crop window centered at (cx, cy), clamped to image bounds
            left = int(round(cx * width - crop_width / 2))
            top = int(round(cy * height - crop_height / 2))
            left = max(0, min(width - crop_width, left))
            top = max(0, min(height - crop_height, top))
            cropped = image.crop((left, top, left + crop_width, top + crop_height))
            zoomed = cropped.resize((width, height), Image.Resampling.LANCZOS)
        new_record = self._save_generated(zoomed, source_type="zoom", source_image_id=image_id)
        return {
            **new_record,
            "factor": float(factor),
            "center_x": cx,
            "center_y": cy,
            "crop_box": [left, top, left + crop_width, top + crop_height],
        }

    def resize_image(self, image_id: str, target_width: int, target_height: int) -> dict[str, Any]:
        width = int(target_width)
        height = int(target_height)
        if width <= 0 or height <= 0:
            raise ValueError("target dimensions must be positive")
        record = self._get_record(image_id)
        with Image.open(record["path"]) as image:
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
        new_record = self._save_generated(resized, source_type="resize", source_image_id=image_id)
        return new_record

    def _register_initial_image(self, image_ref: str) -> str:
        image_path = Path(image_ref)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_ref}")
        image_id = f"image_{self._counter}"
        self._counter += 1
        suffix = image_path.suffix.lower() or ".png"
        local_path = self.work_dir / f"{image_id}{suffix}"
        if image_path.resolve() != local_path.resolve():
            shutil.copy2(image_path, local_path)
        with Image.open(local_path) as image:
            width, height = image.size
        self._images[image_id] = {
            "image_id": image_id,
            "path": str(local_path),
            "width": width,
            "height": height,
            "mime_type": mimetypes.guess_type(str(local_path))[0] or "image/png",
            "source_type": "original",
        }
        return image_id

    def _save_generated(self, image: Image.Image, *, source_type: str, source_image_id: str) -> dict[str, Any]:
        image_id = f"image_{self._counter}"
        self._counter += 1
        path = self.work_dir / f"{image_id}_{source_type}.png"
        image.save(path, format="PNG")
        record = {
            "image_id": image_id,
            "path": str(path),
            "width": image.width,
            "height": image.height,
            "mime_type": "image/png",
            "source_type": source_type,
            "source_image_id": source_image_id,
        }
        self._images[image_id] = record
        return record

    def _get_record(self, image_id: str) -> dict[str, Any]:
        normalized = str(image_id).strip()
        if normalized in self._images:
            return self._images[normalized]
        if normalized.isdigit():
            candidate = f"image_{normalized}"
            if candidate in self._images:
                return self._images[candidate]
        if normalized.lower() == "original" and "image_0" in self._images:
            return self._images["image_0"]
        raise ValueError(f"Unknown image_id: {image_id}")


class RuntimeToolRegistry:
    """Structured tools exposed via function calling."""

    def __init__(
        self,
        image_session: RuntimeImageSession,
        python_executor: LocalPythonExecutor,
        allowed_tools: list[str] | None = None,
    ):
        self.image_session = image_session
        self.python_executor = python_executor
        self.allowed_tools = [str(name).strip() for name in (allowed_tools or []) if str(name).strip()]
        self.allowed_tool_set = set(self.allowed_tools)
        self._handlers = {
            "execute_python": self._execute_python,
            "list_images": self._list_images,
            "get_image_info": self._get_image_info,
            "crop_image": self._crop_image,
            "zoom_image": self._zoom_image,
            "resize_image": self._resize_image,
        }

    def schemas(self) -> list[dict[str, Any]]:
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": "execute_python",
                    "description": "Execute Python code in a persistent interpreter for calculations or verification.",
                    "parameters": {
                        "type": "object",
                        "properties": {"code": {"type": "string"}},
                        "required": ["code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_images",
                    "description": "List images available for the current task, including derived images.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_image_info",
                    "description": "Return path, size, and metadata for an image_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {"image_id": {"type": "string"}},
                        "required": ["image_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "crop_image",
                    "description": "Crop an image using pixel coordinates and create a new derived image.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_id": {"type": "string"},
                            "left": {"type": "integer"},
                            "top": {"type": "integer"},
                            "right": {"type": "integer"},
                            "bottom": {"type": "integer"},
                        },
                        "required": ["image_id", "left", "top", "right", "bottom"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "zoom_image",
                    "description": (
                        "Zoom into a specific location of an image by a factor greater than 1 and create a new derived image. "
                        "center_x and center_y are the normalized coordinates (0.0–1.0) of the zoom target within the image: "
                        "0.0 is the left/top edge, 1.0 is the right/bottom edge. "
                        "For example, to zoom into the upper-right quarter use center_x=0.75, center_y=0.25. "
                        "Defaults to the image center (0.5, 0.5) if omitted."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_id": {"type": "string"},
                            "factor": {"type": "number"},
                            "center_x": {
                                "type": "number",
                                "description": "Horizontal center of zoom target as a fraction of image width [0.0, 1.0]. Default 0.5.",
                            },
                            "center_y": {
                                "type": "number",
                                "description": "Vertical center of zoom target as a fraction of image height [0.0, 1.0]. Default 0.5.",
                            },
                        },
                        "required": ["image_id", "factor"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "resize_image",
                    "description": "Resize an image to the requested width and height and create a new derived image.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_id": {"type": "string"},
                            "target_width": {"type": "integer"},
                            "target_height": {"type": "integer"},
                        },
                        "required": ["image_id", "target_width", "target_height"],
                    },
                },
            },
        ]
        if not self.allowed_tools:
            return schemas
        return [
            schema
            for schema in schemas
            if str(schema.get("function", {}).get("name", "")).strip() in self.allowed_tool_set
        ]

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.allowed_tools and tool_name not in self.allowed_tool_set:
            return self._error_result("UnsupportedTool", f"Tool not enabled for this skill context: {tool_name}")
        handler = self._handlers.get(tool_name)
        if handler is None:
            return self._error_result("UnsupportedTool", f"Unsupported tool: {tool_name}")
        try:
            return handler(arguments)
        except Exception as exc:
            return self._error_result(type(exc).__name__, str(exc))

    def _execute_python(self, arguments: dict[str, Any]) -> dict[str, Any]:
        code = str(arguments.get("code", ""))
        result = self.python_executor.execute_code(code)
        payload = {
            "ok": result.get("error_type") is None,
            "code": code,
            "output": str(result.get("output", "")),
        }
        return {
            "output": json.dumps(payload, ensure_ascii=False),
            "tool_payload": payload,
            "error_type": result.get("error_type"),
        }

    def _list_images(self, arguments: dict[str, Any]) -> dict[str, Any]:
        del arguments
        payload = {"ok": True, "images": self.image_session.list_images()}
        return {"output": json.dumps(payload, ensure_ascii=False), "tool_payload": payload, "error_type": None}

    def _get_image_info(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {"ok": True, **self.image_session.get_image_info(str(arguments.get("image_id", "")))}
        return {"output": json.dumps(payload, ensure_ascii=False), "tool_payload": payload, "error_type": None}

    def _crop_image(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "ok": True,
            **self.image_session.crop_image(
                str(arguments.get("image_id", "")),
                int(arguments.get("left", 0)),
                int(arguments.get("top", 0)),
                int(arguments.get("right", 0)),
                int(arguments.get("bottom", 0)),
            ),
        }
        return self._image_result(payload)

    def _zoom_image(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "ok": True,
            **self.image_session.zoom_image(
                str(arguments.get("image_id", "")),
                float(arguments.get("factor", 0)),
                float(arguments.get("center_x", 0.5)),
                float(arguments.get("center_y", 0.5)),
            ),
        }
        return self._image_result(payload)

    def _resize_image(self, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "ok": True,
            **self.image_session.resize_image(
                str(arguments.get("image_id", "")),
                int(arguments.get("target_width", 0)),
                int(arguments.get("target_height", 0)),
            ),
        }
        return self._image_result(payload)

    @staticmethod
    def _image_result(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "output": json.dumps(payload, ensure_ascii=False),
            "tool_payload": payload,
            "error_type": None,
            "generated_image_path": payload["path"],
            "generated_image_id": payload["image_id"],
        }

    @staticmethod
    def _error_result(error_type: str, message: str) -> dict[str, Any]:
        payload = {"ok": False, "error": message}
        return {
            "output": json.dumps(payload, ensure_ascii=False),
            "tool_payload": payload,
            "error_type": error_type,
        }


def run_function_calling_vqa_case(
    client: VLMClient,
    case: TaskCase,
    benchmark_name: str,
    config: ToolCallingRuntimeConfig | None = None,
) -> AgentResult:
    """Run one benchmark case with a function-calling VQA runtime."""
    runtime_config = config or ToolCallingRuntimeConfig()
    work_dir = runtime_config.work_dir or (Path("artifacts") / "function_calling_vqa" / f"case_{case.case_id}")
    image_session = RuntimeImageSession(work_dir)
    image_refs = _collect_case_images(case)
    image_session.register_initial_images(image_refs)
    skill_context = _resolve_skill_context(case, runtime_config)
    fixed_tool_names = [name.strip() for name in runtime_config.fixed_tool_names if str(name).strip()]
    if fixed_tool_names:
        fixed_set = set(fixed_tool_names)
        skill_context.effective_tool_names = [
            name for name in skill_context.effective_tool_names
            if name in fixed_set
        ]
        skill_context.preferred_tool_names = [
            name for name in skill_context.preferred_tool_names
            if name in fixed_set
        ]
        if not skill_context.effective_tool_names:
            skill_context.effective_tool_names = list(fixed_tool_names)
    tool_registry = RuntimeToolRegistry(
        image_session,
        LocalPythonExecutor(),
        allowed_tools=skill_context.effective_tool_names or None,
    )
    system_prompt = _build_system_prompt(benchmark_name)
    user_prompt = _build_task_prompt(case, include_image=bool(image_refs), skill_context=skill_context)
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for image_ref in image_refs:
        user_content.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(image_ref)}})

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    steps: list[AgentStep] = []
    final_answer = ""

    for turn in range(1, runtime_config.max_iterations + 1):
        request_messages = list(messages)
        raw_response, _ = client.chat_with_tools(
            request_messages,
            tools=tool_registry.schemas() if runtime_config.enable_tools else None,
            settings=runtime_config.model_settings,
            raw_response=True,
        )
        assistant_message = _normalize_assistant_message(raw_response, turn)
        thought = assistant_message.content or ""
        tool_calls = getattr(assistant_message, "tool_calls", None) or []
        if runtime_config.enable_tools and not tool_calls and not thought.strip():
            fallback_text, _ = client.chat(request_messages, runtime_config.model_settings)
            assistant_message = SimpleNamespace(content=fallback_text, tool_calls=None)
            thought = fallback_text or ""
        messages.append(_assistant_message_to_dict(assistant_message))

        if not runtime_config.enable_tools or not tool_calls:
            final_answer = _extract_final_answer(thought)
            steps.append(AgentStep(turn=turn, thought=thought, is_final=True))
            break

        for tool_call in tool_calls:
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            execution_result = tool_registry.execute(tool_call.function.name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": execution_result.get("output", ""),
                }
            )
            artifacts: list[str] = []
            generated_image_path = execution_result.get("generated_image_path")
            generated_image_id = execution_result.get("generated_image_id")
            if generated_image_path:
                artifacts.append(str(generated_image_path))
            steps.append(
                AgentStep(
                    turn=turn,
                    thought=thought,
                    action=AgentAction(name=tool_call.function.name, arguments=arguments),
                    observation=str(execution_result.get("output", "")),
                    artifacts=artifacts,
                )
            )
            if generated_image_path and generated_image_id:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "A derived image was created by a visual tool. "
                                    f"It is available as image_id={generated_image_id}."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": VLMClient.image_data_url(generated_image_path)},
                            },
                        ],
                    }
                )

    if not final_answer and runtime_config.enable_tools:
        raw_response, _ = client.chat_with_tools(
            messages,
            tools=None,
            settings=runtime_config.model_settings,
            raw_response=True,
        )
        assistant_message = _normalize_assistant_message(raw_response, len(steps) + 1)
        thought = assistant_message.content or ""
        final_answer = _extract_final_answer(thought)
        steps.append(AgentStep(turn=len(steps) + 1, thought=thought, is_final=True))

    all_artifacts: list[str] = []
    for step in steps:
        all_artifacts.extend(step.artifacts)

    visible_messages = [
        Message(role=message["role"], content=message["content"])
        for message in messages
        if message.get("role") in {"system", "user", "assistant"}
    ]
    return AgentResult(
        task=case.prompt,
        final_answer=final_answer,
        steps=steps,
        total_turns=len(steps),
        success=bool(final_answer),
        messages=visible_messages,
        all_artifacts=all_artifacts,
        debug_info={
            "skill_names": [skill.name for skill in skill_context.matched_skills],
            "foundation_skill_names": [skill.name for skill in skill_context.foundation_skills],
            "preferred_tool_names": list(skill_context.preferred_tool_names),
            "effective_tool_names": list(skill_context.effective_tool_names),
            "tool_schema_names": [schema["function"]["name"] for schema in tool_registry.schemas()],
        },
    )


def _collect_case_images(case: TaskCase) -> list[str]:
    refs: list[str] = []

    def add_ref(candidate: Any) -> None:
        if not candidate:
            return
        path = str(candidate)
        if path not in refs and os.path.exists(path):
            refs.append(path)

    add_ref(case.image_path)
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    for key in ("image_paths", "all_image_paths"):
        values = metadata.get(key)
        if isinstance(values, (list, tuple)):
            for value in values:
                add_ref(value)
    return refs


def _build_system_prompt(benchmark_name: str) -> str:
    del benchmark_name
    return SYSTEM_PROMPT


def _build_task_prompt(case: TaskCase, include_image: bool, skill_context: ResolvedSkillContext | None = None) -> str:
    choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
    family = str(case.metadata.get("capability_family", "") or "").strip().lower()
    dataset_name = str(case.metadata.get("dataset_name", "") or "").strip().lower()
    lines = [
        "Answer the following benchmark question as accurately as possible.",
        "First write a short reasoning trace based on the visible evidence.",
    ]
    if include_image:
        lines.append("Use the provided image(s) when relevant.")
    if skill_context and skill_context.prompt_blocks:
        lines.extend(["", "Skill Context:"])
        for note in skill_context.routing_notes:
            lines.append(f"- {note}")
        for block in skill_context.prompt_blocks:
            lines.extend(["", block])
    if dataset_name in {"vstar", "hrbench"}:
        lines.append("If the question provides labeled options, return only the matching option letter in Final answer.")
    elif dataset_name == "mathvista" and choices:
        lines.append("If the question provides labeled options, return only the matching option letter in Final answer.")
    elif dataset_name == "chartqa":
        lines.extend(
            [
                "Read the chart carefully before answering.",
                "Identify which chart region (bar, line, legend, axis label) contains the needed value.",
                "Use zoom_image with center_x/center_y targeting that region — legends are often top-right (center_y≈0.1), x-axis labels at the bottom (center_y≈0.9), y-axis labels at the left (center_x≈0.08).",
                "Extract the numeric values first, then use execute_python for arithmetic.",
                "Return the final numeric value or short text directly in Final answer — do not return an option letter.",
            ]
        )
    elif dataset_name == "mathvista":
        lines.extend(
            [
                "Identify the relevant values or geometric properties in the figure.",
                "Use zoom_image with center_x/center_y if tick marks, annotations, or diagram labels are too small to read.",
                "Use execute_python after extracting all needed values — always print() the result.",
                "If the question is free-form, return the final numeric or textual answer directly in Final answer.",
            ]
        )
    elif dataset_name == "hrbench":
        lines.extend(
            [
                "HRBench images are high-resolution — always use zoom_image before answering.",
                "Estimate where the target text or symbol is located and set center_x/center_y accordingly (do not default to 0.5 if the target is off-center).",
                "Use factor=3 or higher for small or distant text; use a two-pass zoom if the target location is uncertain.",
                "Use crop_image after zoom if surrounding distractors make the target hard to identify.",
                "Return the matching option letter in Final answer.",
            ]
        )
    if family == "vstar_direct_attributes":
        lines.extend(
            [
                "The target object is often small or off-center. Always call zoom_image unless the target is unambiguously large.",
                "Set center_x and center_y to where the target object appears in the image (normalized 0.0–1.0). Do NOT leave them at 0.5 if the target is off-center.",
                "Example: target in upper-right → center_x=0.75, center_y=0.25. Target lower-left → center_x=0.25, center_y=0.75.",
                "If the first zoom does not show the target, re-estimate the position and call zoom_image again.",
                "Verify the named object carefully before choosing among similar colors or materials.",
            ]
        )
    elif family == "vstar_relative_position":
        lines.extend(
            [
                "Judge the spatial relation from the viewer's perspective using the full image as the reference frame.",
                "If an object is too small to localize, use zoom_image with center_x/center_y at its estimated position — then reason about the relation in the full-image frame.",
                "Never let a zoomed patch become the new reference frame for left/right judgment.",
                "First determine the semantic spatial conclusion, then map it to the matching option letter.",
            ]
        )
    elif dataset_name == "chartqa":
        lines.extend(
            [
                "Do not zoom to the image center if the target (legend, axis label, specific bar) is in a corner or edge.",
                "Confirm the category or series label before reading the numeric value to avoid confusing adjacent bars or lines.",
                "For comparisons or differences, extract both values explicitly before computing.",
            ]
        )
    elif dataset_name == "mathvista":
        lines.extend(
            [
                "Work from visible evidence in the figure — do not estimate values that are readable.",
                "For geometry: zoom to vertices or edge labels where angle/length annotations appear.",
                "For graphs and plots: x-axis labels are at center_y≈0.90, y-axis labels at center_x≈0.08.",
            ]
        )
    elif dataset_name == "hrbench":
        lines.extend(
            [
                "If you are uncertain of the target location, do a first-pass zoom (factor=2, center=0.5) to orient yourself, then a second targeted zoom.",
                "Prioritize reading the exact text or symbol — do not infer the answer from surrounding context alone.",
                "After reading the target, verify it matches one of the answer options before committing.",
            ]
        )
    lines.extend(["", f"Question: {case.prompt}"])
    if choices and not _question_embeds_choices(case.prompt, choices):
        lines.extend(["", "Choices:"])
        for label, text in sorted(choices.items()):
            lines.append(f"({label}) {text}")
    lines.extend(
        [
            "",
            "End with a final line in the format: Final answer: <answer>",
        ]
    )
    return "\n".join(lines)


def _resolve_skill_context(case: TaskCase, config: ToolCallingRuntimeConfig) -> ResolvedSkillContext:
    if not config.use_skills:
        return ResolvedSkillContext()
    skill_roots = resolve_skill_roots(config.capability_root, config.static_skills_dir)
    if not skill_roots:
        return ResolvedSkillContext()
    resolver = SkillResolver(skill_roots)
    return resolver.resolve(case)


def _question_embeds_choices(question: str, choices: dict[str, Any]) -> bool:
    embedded = 0
    for label in choices:
        token = str(label).strip().upper()
        if f"({token})" in question or f"\n{token}." in question or f"\n{token})" in question:
            embedded += 1
    return embedded >= 2


def _assistant_message_to_dict(assistant_message: Any) -> dict[str, Any]:
    message = {"role": "assistant", "content": assistant_message.content or ""}
    tool_calls = getattr(assistant_message, "tool_calls", None) or []
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ]
    return message


def _normalize_assistant_message(raw_response: Any, iteration: int) -> Any:
    if hasattr(raw_response, "choices"):
        return raw_response.choices[0].message

    if not isinstance(raw_response, dict):
        return SimpleNamespace(content="", tool_calls=None)

    data = raw_response.get("data")
    if isinstance(data, dict):
        message = data.get("message")
        if isinstance(message, dict) and message.get("is_function_call"):
            return SimpleNamespace(
                content=None,
                tool_calls=[
                    SimpleNamespace(
                        id=f"proxy_call_{iteration}",
                        function=SimpleNamespace(
                            name=message.get("function_call_name", ""),
                            arguments=message.get("function_call_args", "{}"),
                        ),
                    )
                ],
            )

        completion = data.get("completion")
        if isinstance(completion, dict):
            choices = completion.get("choices")
            if isinstance(choices, list) and choices:
                choice_message = (choices[0] or {}).get("message", {})
                if isinstance(choice_message, dict):
                    raw_tool_calls = choice_message.get("tool_calls") or []
                    tool_calls = [
                        SimpleNamespace(
                            id=str(call.get("id", f"proxy_call_{iteration}")),
                            function=SimpleNamespace(
                                name=str((call.get("function") or {}).get("name", "")),
                                arguments=str((call.get("function") or {}).get("arguments", "{}")),
                            ),
                        )
                        for call in raw_tool_calls
                        if isinstance(call, dict)
                    ]
                    return SimpleNamespace(
                        content=choice_message.get("content"),
                        tool_calls=tool_calls or None,
                    )

        if isinstance(message, str):
            return SimpleNamespace(content=message, tool_calls=None)

    return SimpleNamespace(content="", tool_calls=None)


def _extract_final_answer(text: str) -> str:
    match = re.search(r"Final answer:\s*(.+)$", text or "", re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return (text or "").strip()
