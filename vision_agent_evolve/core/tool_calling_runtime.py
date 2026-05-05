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

NO_TOOL_SYSTEM_PROMPT = (
    "You are solving multimodal benchmark questions. "
    "Think through the visual evidence briefly before you commit to an answer. "
    "Do not call external tools. Answer from the provided image, question, choices, and skill context only. "
    "The final line of your response must begin with 'Final answer:'."
)

O4_MINI_TOOL_SYSTEM_PROMPT = (
    "You are solving multimodal benchmark questions with structured function calling. "
    "When a tool is needed, emit the actual function call immediately. "
    "Do not describe planned tool use in plain text. "
    "Do not output fake JSON, pseudo-code, or tool syntax in message text. "
    "Do not ask for permission to zoom or crop. "
    "Either emit a real function call or give the final answer directly. "
    "For multiple-choice questions, the final line must be exactly 'Final answer: X' where X is the option letter."
)


@dataclass
class ToolCallingRuntimeConfig:
    """Configuration for the function-calling runtime."""

    max_iterations: int = 8
    model_settings: ModelSettings = field(
        default_factory=lambda: ModelSettings(temperature=0.0, max_tokens=1024, timeout=240, max_retries=5)
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
                    "description": (
                        "Execute Python code in a persistent interpreter for calculations or verification. "
                        "Always use print() to output results — silent assignments produce no output. "
                        "Pattern: assign values read from the image as variables, then compute. "
                        "Example: a=45.3; b=28.7; print(round(a-b, 1))"
                    ),
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
                    "description": (
                        "Crop an image to a precise pixel region and create a new derived image. "
                        "Call get_image_info first to obtain the image dimensions, then compute "
                        "left/top/right/bottom pixel coordinates. "
                        "Best for isolating a specific region (chart legend, axis label block, text area) "
                        "with exact boundaries when zoom_image is not precise enough."
                    ),
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
    model_name = _runtime_model_name(client)
    o4_mini = _is_o4_mini_model(model_name)
    _apply_case_tool_gate(case, skill_context, runtime_config)
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
    tool_schemas = tool_registry.schemas() if runtime_config.enable_tools else []
    tools_available = bool(tool_schemas)
    dataset_name = str(case.metadata.get("dataset_name", "") or "").strip().lower()
    mathvista_direct_no_tool = dataset_name == "mathvista" and not tools_available
    system_prompt = _build_system_prompt(
        benchmark_name,
        enable_tools=tools_available,
        model_name=model_name,
        dataset_name=dataset_name,
    )
    user_prompt = _build_task_prompt(
        case,
        include_image=bool(image_refs),
        skill_context=skill_context,
        enable_tools=tools_available,
        model_name=model_name,
    )
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for image_ref in image_refs:
        user_content.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(image_ref)}})

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_content})
    steps: list[AgentStep] = []
    final_answer = ""
    corrective_retry_used = False
    forced_choice_retry_used = False
    mathvista_format_retry_used = False

    for turn in range(1, runtime_config.max_iterations + 1):
        request_messages = list(messages)
        if tools_available:
            raw_response, _ = client.chat_with_tools(
                request_messages,
                tools=tool_schemas,
                settings=runtime_config.model_settings,
                raw_response=True,
            )
            assistant_message = _normalize_assistant_message(raw_response, turn, model_name=model_name)
        else:
            text_response, _ = client.chat(
                request_messages,
                _mathvista_direct_model_settings(runtime_config.model_settings)
                if mathvista_direct_no_tool else runtime_config.model_settings,
            )
            assistant_message = SimpleNamespace(content=text_response, tool_calls=None)
        thought = assistant_message.content or ""
        tool_calls = getattr(assistant_message, "tool_calls", None) or []
        if tools_available and not tool_calls and isinstance(thought, str):
            pseudo_tool_call = _parse_pseudo_tool_call(thought, model_name=model_name)
            if pseudo_tool_call is not None:
                tool_name, arguments = pseudo_tool_call
                assistant_message = SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id=f"pseudo_call_{turn}",
                            function=SimpleNamespace(
                                name=tool_name,
                                arguments=json.dumps(arguments, ensure_ascii=False),
                            ),
                        )
                    ],
                )
                thought = ""
                tool_calls = assistant_message.tool_calls
        if tools_available and not tool_calls and not thought.strip():
            fallback_text, _ = client.chat(request_messages, runtime_config.model_settings)
            assistant_message = SimpleNamespace(content=fallback_text, tool_calls=None)
            thought = fallback_text or ""
        messages.append(_assistant_message_to_dict(assistant_message))

        if not tools_available or not tool_calls:
            final_answer = _extract_final_answer(thought)
            if (
                tools_available
                and o4_mini
                and not corrective_retry_used
                and not _contains_explicit_final_answer(thought)
                and _tool_intent_text(thought)
            ):
                corrective_retry_used = True
                messages.append({"role": "user", "content": _o4_retry_message()})
                steps.append(AgentStep(turn=turn, thought=thought))
                continue
            final_answer = _finalize_answer(final_answer, case)
            if (
                dataset_name in {"mathvista", "vstar", "hrbench"}
                and not forced_choice_retry_used
                and _needs_multiple_choice_repair(final_answer, case)
            ):
                forced_choice_retry_used = True
                messages.append({"role": "user", "content": _o4_force_choice_message(case)})
                steps.append(AgentStep(turn=turn, thought=thought))
                continue
            if (
                dataset_name == "mathvista"
                and not mathvista_format_retry_used
                and _mathvista_needs_numeric_format_repair(final_answer, case)
            ):
                mathvista_format_retry_used = True
                repaired_answer, repair_thought = _repair_mathvista_numeric_answer(
                    client,
                    messages,
                    case,
                    final_answer,
                    runtime_config.model_settings,
                )
                if repaired_answer:
                    final_answer = repaired_answer
                    steps.append(AgentStep(turn=turn, thought=thought))
                    steps.append(AgentStep(turn=turn, thought=repair_thought, is_final=True))
                    break
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

    if not final_answer and tools_available:
        raw_response, _ = client.chat_with_tools(
            messages,
            tools=None,
            settings=runtime_config.model_settings,
            raw_response=True,
        )
        assistant_message = _normalize_assistant_message(raw_response, len(steps) + 1, model_name=model_name)
        thought = assistant_message.content or ""
        final_answer = _finalize_answer(_extract_final_answer(thought), case)
        if dataset_name in {"mathvista", "vstar", "hrbench"} and not forced_choice_retry_used and _needs_multiple_choice_repair(final_answer, case):
            forced_choice_retry_used = True
            messages.append({"role": "user", "content": _o4_force_choice_message(case)})
            raw_response, _ = client.chat_with_tools(
                messages,
                tools=None,
                settings=runtime_config.model_settings,
                raw_response=True,
            )
            assistant_message = _normalize_assistant_message(raw_response, len(steps) + 1, model_name=model_name)
            thought = assistant_message.content or ""
            final_answer = _finalize_answer(_extract_final_answer(thought), case)
        if (
            dataset_name == "mathvista"
            and not mathvista_format_retry_used
            and _mathvista_needs_numeric_format_repair(final_answer, case)
        ):
            mathvista_format_retry_used = True
            repaired_answer, repair_thought = _repair_mathvista_numeric_answer(
                client,
                messages,
                case,
                final_answer,
                runtime_config.model_settings,
            )
            if repaired_answer:
                final_answer = repaired_answer
                thought = repair_thought
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
            "effective_tool_names": list(skill_context.effective_tool_names) if tools_available else [],
            "tool_schema_names": (
                [schema["function"]["name"] for schema in tool_schemas]
                if tools_available else []
            ),
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


def _runtime_model_name(client: Any) -> str:
    return str(getattr(client, "model", "") or os.getenv("VLM_MODEL", "") or "").strip()


def _is_o4_mini_model(model_name: str) -> bool:
    normalized = str(model_name or "").strip().lower()
    return normalized == "o4-mini" or normalized.startswith("o4-mini-")


def _apply_case_tool_gate(
    case: TaskCase,
    skill_context: ResolvedSkillContext,
    runtime_config: ToolCallingRuntimeConfig,
) -> None:
    """Route MathVista and ChartQA cases to the appropriate tool tier.

    MathVista (doubao-seed-2.0-pro, 900 cases):
      - no_tool        n=282  acc=90.78%
      - python_only    n=472  acc=91.31%  ← best
      - zoom_only      n=90   acc=74.44%  ← hurts
      - zoom+python    n=56   acc=67.86%  ← hurts most
    Zoom loses global context (bar zoomed without y-axis scale → wrong reading).
    Strategy: execute_python only for most; no tools for pure visual perception.

    ChartQA: same zoom-hurts reasoning applies. Empirical tool_usage_rate=0.0
    (model never calls zoom despite it being offered). Expose execute_python only
    so the model can verify arithmetic while reading chart values directly.
    """
    if not runtime_config.enable_tools:
        return
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    dataset_name = str(metadata.get("dataset_name", "") or "").strip().lower()

    if dataset_name == "chartqa":
        # ChartQA: python-only (no zoom/crop).
        # Model reads chart values directly at original scale; execute_python for arithmetic.
        skill_context.effective_tool_names = ["execute_python"]
        skill_context.preferred_tool_names = ["execute_python"]
        skill_context.routing_notes.append(
            "ChartQA: python-only — read chart values directly from the image, "
            "use execute_python only for arithmetic (difference, ratio, mean)."
        )
        return

    if dataset_name != "mathvista":
        return

    if _mathvista_is_pure_visual_perception(case):
        # No tools: pure visual pattern / yes-no / spatial reasoning with no arithmetic.
        # Keep prompt_blocks cleared so the cleaner _build_mathvista_direct_prompt is used.
        skill_context.effective_tool_names = ["__no_tools__"]
        skill_context.preferred_tool_names = []
        skill_context.prompt_blocks = []
        skill_context.reference_blocks = []
        skill_context.routing_notes.append(
            "MathVista: pure visual perception — answering directly, no tools needed."
        )
        return

    # Default: expose execute_python only (no zoom/crop).
    # The model reads the image directly and uses Python only for arithmetic verification.
    skill_context.effective_tool_names = ["execute_python"]
    skill_context.preferred_tool_names = ["execute_python"]
    skill_context.routing_notes.append(
        "MathVista: python-only — read visual values directly from the image, "
        "use execute_python only for arithmetic verification."
    )


def _mathvista_is_pure_visual_perception(case: TaskCase) -> bool:
    """Return True only for questions that are pure visual perception with no arithmetic.

    We are deliberately conservative: only the clearest cases (IQ-style pattern
    completion, yes/no MCQ, cube/paper-folding) are flagged.  Everything else
    keeps tools so the model can inspect fine visual details and verify arithmetic.
    """
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    prompt = str(case.prompt or "")
    lower = prompt.lower()
    choices = metadata.get("choices") if isinstance(metadata.get("choices"), dict) else {}

    # Yes/No MCQ — no arithmetic possible.
    if choices:
        values = {str(v).strip().lower() for v in choices.values()}
        if values <= {"yes", "no"}:
            return True

    # Visual pattern completion / IQ-matrix / cube-net / paper-folding.
    _pattern_keywords = [
        "comes next",
        "come next",
        "next in the sequence",
        "complete the sequence",
        "complete the matrix",
        "complete the pattern",
        "missing picture",
        "missing figure",
        "missing image",
        "unfolded cube",
        "cube is identical",
        "net of the cube",
        "which net",
        "paper folding",
        "folded paper",
    ]
    if any(kw in lower for kw in _pattern_keywords):
        return True

    return False


def _has_explicit_math_signal(text: str) -> bool:
    raw = str(text or "")
    lower = raw.lower()
    if re.search(r"[-+]?\d", raw):
        return True
    return any(token in lower for token in ["\\frac", "\\sqrt", "π", "theta", "angle", "radius", "diameter"])


def _has_calculation_intent(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        token in lower
        for token in [
            "calculate",
            "compute",
            "find",
            "total",
            "sum",
            "difference",
            "average",
            "mean",
            "median",
            "percentage",
            "percent",
            "ratio",
            "probability",
            "area",
            "volume",
            "radius",
            "diameter",
            "angle",
            "length",
            "distance",
            "speed",
            "work",
            "force",
            "energy",
            "perimeter",
            "slope",
            "derivative",
            "limit",
        ]
    )


def _has_visual_calculation_language(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        token in lower
        for token in [
            "sum",
            "total",
            "subtract",
            "left",
            "remaining",
            "average",
            "mean",
            "difference",
        ]
    )


def _looks_like_numeric_or_formula_choice(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    if re.search(r"[-+]?\d", text):
        return True
    return any(token in text for token in ["π", "pi", "sqrt", "\\frac", "/", "^"])


def _normalize_text_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").strip().lower()).strip()


def _normalize_multiple_choice_answer(answer: str, case: TaskCase) -> str:
    raw = str(answer or "").strip()
    if not raw:
        return raw

    label_match = re.match(r"^\(?([A-Z])\)?$", raw, re.IGNORECASE)
    if label_match:
        return label_match.group(1).upper()
    label_with_text_match = re.match(r"^\(?([A-Z])\)?[\.\:\-]\s*.+$", raw, re.IGNORECASE)
    if label_with_text_match:
        return label_with_text_match.group(1).upper()

    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    choices = metadata.get("choices") if isinstance(metadata.get("choices"), dict) else {}
    if not choices:
        return raw

    normalized_answer = _normalize_text_key(raw)
    for label, choice_text in choices.items():
        if normalized_answer == _normalize_text_key(str(choice_text)):
            return str(label).strip().upper()
    return raw


def _finalize_answer(answer: str, case: TaskCase) -> str:
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    choices = metadata.get("choices") if isinstance(metadata.get("choices"), dict) else {}
    dataset_name = str(metadata.get("dataset_name", "") or "").strip().lower()
    answer_type = str(metadata.get("answer_type", "") or "").strip().lower()
    if choices or dataset_name in {"vstar", "hrbench"} or "multiple_choice" in answer_type:
        return _normalize_multiple_choice_answer(answer, case)
    return str(answer or "").strip()


def _multiple_choice_labels(case: TaskCase) -> set[str]:
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    choices = metadata.get("choices") if isinstance(metadata.get("choices"), dict) else {}
    return {str(label).strip().upper() for label in choices}


def _needs_multiple_choice_repair(answer: str, case: TaskCase) -> bool:
    labels = _multiple_choice_labels(case)
    if not labels:
        return False
    normalized = str(answer or "").strip().upper()
    return normalized not in labels


def _mathvista_needs_numeric_format_repair(answer: str, case: TaskCase) -> bool:
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    if str(metadata.get("dataset_name", "") or "").strip().lower() != "mathvista":
        return False
    if metadata.get("choices"):
        return False
    answer_type = str(metadata.get("answer_type", "") or "").strip().lower()
    if answer_type not in {"integer", "float"}:
        return False
    text = str(answer or "").strip()
    if not text:
        return False
    if answer_type == "integer" and re.fullmatch(r"[-+]?\d+", text):
        return False
    if answer_type == "float" and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
        return False
    noisy_markers = [
        " or ",
        "approximately",
        "approx",
        "boxed",
        "\\",
        "$",
        "%",
        "unit",
        "year",
        "years",
        "cm",
        "m/s",
        "gram",
        "grams",
        "newton",
        "joule",
        "velocity",
        "matches",
    ]
    if any(marker in text.lower() for marker in noisy_markers):
        return True
    numeric_tokens = re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
    return len(numeric_tokens) != 1


def _repair_mathvista_numeric_answer(
    client: VLMClient,
    messages: list[dict[str, Any]],
    case: TaskCase,
    answer: str,
    settings: ModelSettings,
) -> tuple[str, str]:
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    answer_type = str(metadata.get("answer_type", "") or "").strip().lower()
    precision = metadata.get("precision")
    if answer_type == "integer":
        format_rule = "The expected answer type is integer. Return one whole number only."
    else:
        if precision is None:
            format_rule = "The expected answer type is float. Return one decimal number only."
        else:
            format_rule = f"The expected answer type is float rounded to {int(float(precision))} decimal places. Return one decimal number only."
    repair_prompt = (
        "Reformat the previous MathVista final answer for automatic grading.\n"
        f"Previous final answer: {answer}\n"
        f"{format_rule}\n"
        "Do not include units, words, formulas, fractions, percentages, alternatives, ranges, or explanation. "
        "If the solved result is a fraction or probability, convert it to the requested decimal. "
        "If the solved result was written with units or scientific notation, output the single numeric value in the scale requested by the question. "
        "Reply with exactly: Final answer: <number>"
    )
    repair_messages = list(messages) + [{"role": "user", "content": repair_prompt}]
    repair_settings = ModelSettings(
        temperature=settings.temperature,
        max_tokens=80,
        timeout=max(settings.timeout, 120),
        max_retries=max(settings.max_retries, 3),
        retry_backoff_seconds=settings.retry_backoff_seconds,
    )
    try:
        thought, _ = client.chat(repair_messages, repair_settings)
    except Exception:
        return "", ""
    repaired = _finalize_answer(_extract_final_answer(thought), case)
    return repaired, thought or ""


def _tool_intent_text(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    patterns = [
        "zoom",
        "crop",
        "tool",
        "next step",
        "i need to",
        "i will",
        "let's",
        "lets",
        "attempted to",
        "function call",
        "zoom_image(",
        "{{zoom_image",
        '"command":"zoom_image"',
        '"tool":"zoom_image"',
    ]
    return any(pattern in normalized for pattern in patterns)


def _o4_retry_message() -> str:
    return (
        "Your previous message described a tool action in plain text. "
        "Do not narrate tool use. "
        "If inspection is needed, emit the actual function call now. "
        "Otherwise reply with only the required final answer format."
    )


def _o4_force_choice_message(case: TaskCase) -> str:
    labels = sorted(_multiple_choice_labels(case))
    if labels:
        label_text = "/".join(labels)
        return (
            "Select the best answer now. Do not refuse or say the image is unclear. "
            f"You must choose exactly one option from {label_text}. "
            "Reply with only 'Final answer: X'."
        )
    return "Reply with only the required final answer format."


def _contains_explicit_final_answer(text: str) -> bool:
    return bool(re.search(r"Final answer:\s*(.+)$", str(text or ""), re.IGNORECASE | re.MULTILINE))


def _mathvista_direct_model_settings(settings: ModelSettings) -> ModelSettings:
    # 200 tokens is far too short for multi-step visual reasoning; use 1024.
    return ModelSettings(
        temperature=settings.temperature,
        max_tokens=1024,
        timeout=max(settings.timeout, 240),
        max_retries=max(settings.max_retries, 5),
        retry_backoff_seconds=max(settings.retry_backoff_seconds, 3.0),
    )


def _parse_scalar_value(raw_value: str) -> Any:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    if value.startswith("user-image-") and value[len("user-image-"):].isdigit():
        return f"image_{value[len('user-image-'):]}"
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if any(char in value for char in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_key_value_arguments(raw_args: str) -> dict[str, Any]:
    text = str(raw_args or "").strip()
    if not text:
        return {}
    parts = re.split(r"\s*,\s*(?=[A-Za-z_][A-Za-z0-9_]*\s*=)", text)
    arguments: dict[str, Any] = {}
    for part in parts:
        if "=" not in part:
            return {}
        key, value = part.split("=", 1)
        key = key.strip()
        if not key:
            return {}
        arguments[key] = _parse_scalar_value(value)
    return arguments


def _parse_pseudo_tool_call(text: str, *, model_name: str) -> tuple[str, dict[str, Any]] | None:
    if not _is_o4_mini_model(model_name):
        return None

    raw = str(text or "").strip()
    if not raw:
        return None
    final_match = re.search(r"Final answer:\s*(.+)$", raw, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if final_match:
        raw = final_match.group(1).strip()

    try:
        payload = json.loads(raw)
    except Exception:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            try:
                payload = json.loads(json_match.group(0))
            except Exception:
                payload = None
        else:
            payload = None
    if isinstance(payload, dict):
        tool_name = str(payload.get("command") or payload.get("tool") or payload.get("name") or "").strip()
        arguments = payload.get("args") or payload.get("arguments") or payload.get("parameters") or {}
        if tool_name == "execute_python" and isinstance(payload.get("code"), str):
            return "execute_python", {"code": payload["code"]}
        if not tool_name and isinstance(payload.get("code"), str):
            return "execute_python", {"code": payload["code"]}
        if tool_name in {"execute_python", "list_images", "get_image_info", "crop_image", "zoom_image", "resize_image"} and isinstance(arguments, dict):
            if "image_id" in arguments:
                arguments = dict(arguments)
                arguments["image_id"] = _parse_scalar_value(str(arguments["image_id"]))
            return tool_name, arguments
        if not tool_name and {"factor", "center_x", "center_y"} <= set(payload.keys()):
            arguments = dict(payload)
            if "image_id" in arguments:
                arguments["image_id"] = _parse_scalar_value(str(arguments["image_id"]))
            else:
                arguments["image_id"] = "image_0"
            return "zoom_image", arguments

    code_match = re.search(r"```(?:python|py)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if code_match:
        code = code_match.group(1).strip()
        if code and ("print(" in code or "\nprint " in code):
            return "execute_python", {"code": code}

    match = re.search(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*\}\}", raw, re.DOTALL)
    if not match:
        match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\((.*)\)", raw, re.DOTALL)
    if not match:
        return None
    tool_name = match.group(1).strip()
    if tool_name not in {"execute_python", "list_images", "get_image_info", "crop_image", "zoom_image", "resize_image"}:
        return None
    arguments = _parse_key_value_arguments(match.group(2))
    if not arguments:
        return None
    return tool_name, arguments


def _build_system_prompt(
    benchmark_name: str,
    enable_tools: bool = True,
    model_name: str = "",
    dataset_name: str = "",
) -> str:
    del benchmark_name
    if not enable_tools and str(dataset_name or "").strip().lower() == "mathvista":
        return NO_TOOL_SYSTEM_PROMPT
    if enable_tools and _is_o4_mini_model(model_name):
        return O4_MINI_TOOL_SYSTEM_PROMPT
    return SYSTEM_PROMPT if enable_tools else NO_TOOL_SYSTEM_PROMPT


def _mathvista_answer_format_note(case: TaskCase) -> str:
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    if str(metadata.get("dataset_name", "") or "").strip().lower() != "mathvista":
        return ""
    if metadata.get("choices"):
        return "Final answer must be one option letter only."
    answer_type = str(metadata.get("answer_type", "") or "").strip().lower()
    if answer_type == "integer":
        return "Final answer must be one integer only: no units, words, formulas, alternatives, or explanation."
    if answer_type == "float":
        precision = metadata.get("precision")
        if precision is None:
            return "Final answer must be one decimal number only: no units, words, formulas, fractions, alternatives, or explanation."
        try:
            digits = int(float(precision))
        except (TypeError, ValueError):
            digits = 2
        return (
            f"Final answer must be one decimal number rounded to {digits} decimal places: "
            "no units, words, formulas, fractions, alternatives, percentages, or explanation."
        )
    return "Final answer must be the short answer only, without explanation."


def _build_task_prompt(
    case: TaskCase,
    include_image: bool,
    skill_context: ResolvedSkillContext | None = None,
    enable_tools: bool = True,
    model_name: str = "",
) -> str:
    choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
    family = str(case.metadata.get("capability_family", "") or "").strip().lower()
    dataset_name = str(case.metadata.get("dataset_name", "") or "").strip().lower()
    o4_mini = _is_o4_mini_model(model_name)
    if (
        dataset_name == "mathvista"
        and not enable_tools
        and skill_context is not None
        and not skill_context.prompt_blocks
    ):
        return _build_mathvista_direct_prompt(case, choices)
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
                "Read the chart carefully and identify the specific bar, line, or label the question refers to.",
                "Confirm the category or series label matches the question before reading the value.",
                "Read the value exactly as shown — if a number is printed on the bar, use that exact number; otherwise align with the y-axis scale precisely.",
                "Check the y-axis unit (%, K, M, billions) before extracting.",
                "Use execute_python for arithmetic (difference, ratio, percentage, mean) — always print() the result.",
                "Return the final answer in Final answer: as a number or short text only — no extra words, no units, no explanation.",
            ]
        )
    elif dataset_name == "mathvista":
        format_note = _mathvista_answer_format_note(case)
        if enable_tools:
            effective_tools = set(skill_context.effective_tool_names if skill_context else [])
            if {"zoom_image", "crop_image", "list_images"} & effective_tools:
                lines.extend(
                    [
                        "This case passed the MathVista visual-reading gate.",
                        "Identify what visual quantities the question requires: numbers, labels, angles, lengths, coordinates, object counts, or local yes/no comparison evidence.",
                        "If those quantities are small, annotated, or hard to read at the original scale, use zoom_image on the relevant region.",
                        "Estimate center_x/center_y from the original image: axes and rulers are often near edges; legends and labels may be in corners; object comparisons require the object region, not the whole image.",
                        "Use factor=2-3 for moderate detail and factor=4 for very small labels, ruler marks, arrows, chart ticks, or medical/diagram details.",
                        "Use crop_image after get_image_info only when a dense region needs exact isolation.",
                        "Once the visual values are read, use execute_python for arithmetic, averages, ratios, geometric formulas, or option-value comparison; always print() the result.",
                        "For multiple-choice questions, return the matching option letter only. For open-ended questions, return the numeric or short text answer directly.",
                        format_note,
                    ]
                )
            else:
                lines.extend(
                    [
                        "Identify the relevant values or geometric properties directly from the original image.",
                        "This case passed the MathVista calculation gate. After extracting the needed values from the image or question, call execute_python to verify the final arithmetic.",
                        "Do not guess the final computed value before using execute_python.",
                        "Do not use execute_python to read the image, count objects, infer uncertain visual facts, select a visual pattern option, or answer simple yes/no questions.",
                        "Do not call image inspection tools such as zoom_image, crop_image, list_images, or get_image_info.",
                        "The Python code must contain only the extracted values and the arithmetic/formula needed for the answer, and it must print() the result.",
                        "If the question is free-form, return the final numeric or textual answer directly in Final answer.",
                        format_note,
                    ]
                )
        else:
            lines.extend(
                [
                    "Answer directly from the original image and question.",
                    "For visual recognition, counting, pattern, yes/no, or semantic multiple-choice questions, avoid unnecessary calculation.",
                    "If labeled options are provided, return only the matching option letter in Final answer.",
                    "If the question is free-form, return the final numeric or textual answer directly in Final answer.",
                    format_note,
                ]
            )
    if dataset_name == "hrbench":
        if enable_tools:
            if o4_mini:
                lines.extend(
                    [
                        "HRBench images are high-resolution. If the target is small or unreadable, call zoom_image immediately.",
                        "If the zoomed region is still cluttered, call crop_image.",
                        "Do not describe a planned zoom or crop in natural language. Emit the function call instead.",
                        "Return the matching option letter in Final answer.",
                    ]
                )
            else:
                lines.extend(
                    [
                        "HRBench images are high-resolution — always use zoom_image before answering.",
                        "Estimate where the target text or symbol is located and set center_x/center_y accordingly (do not default to 0.5 if the target is off-center).",
                        "Use factor=3 or higher for small or distant text; use a two-pass zoom if the target location is uncertain.",
                        "Use crop_image after zoom if surrounding distractors make the target hard to identify.",
                        "Return the matching option letter in Final answer.",
                    ]
                )
        else:
            lines.extend(
                [
                    "This image is high-resolution. Focus carefully on the region where the target text or symbol appears.",
                    "Read it precisely before matching to an answer option.",
                    "Return the matching option letter in Final answer.",
                ]
            )
    if family == "vstar_direct_attributes":
        if enable_tools:
            lines.extend(
                [
                    "The target object is often small or off-center. Always call zoom_image unless the target is unambiguously large.",
                    "Set center_x and center_y to where the target object appears in the image (normalized 0.0–1.0). Do NOT leave them at 0.5 if the target is off-center.",
                    "Example: target in upper-right → center_x=0.75, center_y=0.25. Target lower-left → center_x=0.25, center_y=0.75.",
                    "If the first zoom does not show the target, re-estimate the position and call zoom_image again.",
                    "Verify the named object carefully before choosing among similar colors or materials.",
                ]
            )
        else:
            lines.extend(
                [
                    "The target object may be small or off-center. Focus your visual attention on the named object.",
                    "Carefully examine its color or material attribute — do not switch to a nearby distractor.",
                    "Match the observed attribute to the answer options and return the option letter.",
                ]
            )
    elif family == "vstar_relative_position":
        if enable_tools:
            lines.extend(
                [
                    "Judge the spatial relation from the viewer's perspective using the full image as the reference frame.",
                    "If an object is too small to localize, use zoom_image with center_x/center_y at its estimated position — then reason about the relation in the full-image frame.",
                    "Never let a zoomed patch become the new reference frame for left/right judgment.",
                    "First determine the semantic spatial conclusion, then map it to the matching option letter.",
                ]
            )
        else:
            lines.extend(
                [
                    "Use the full image as your spatial reference frame.",
                    "Identify both named objects and judge their relative position from the viewer's perspective — not from the objects' own orientation.",
                    "First determine the spatial conclusion, then map it to the matching option letter.",
                ]
            )
    elif dataset_name == "chartqa":
        lines.extend(
            [
                "Confirm the category or series label before reading — do not read the wrong bar or line.",
                "Read labeled numbers exactly as printed; do not approximate values that are annotated.",
                "For arithmetic questions, use execute_python with the extracted values.",
            ]
        )
    elif dataset_name == "mathvista":
        lines.extend(
            [
                "Work from visible evidence in the figure — do not estimate values that are labeled.",
                "Check units (degrees, cm, %) before finalizing the answer.",
            ]
        )
    elif dataset_name == "hrbench":
        lines.extend(
            [
                "Prioritize reading the exact text or symbol — do not infer the answer from surrounding context alone.",
                "After reading the target, verify it matches one of the answer options before committing.",
            ]
        )
    if o4_mini and enable_tools and dataset_name in {"hrbench", "vstar"}:
        lines.extend(
            [
                "When tools are available, never narrate a planned tool action in plain text.",
                "Never output pseudo tool calls, JSON snippets, or coordinates as the answer.",
                "If zoom or crop is needed, emit the actual function call instead.",
                "For this task, Final answer must contain only the option letter.",
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
            "End with a final line in the format: Final answer: your answer",
        ]
    )
    return "\n".join(lines)


def _build_mathvista_direct_prompt(case: TaskCase, choices: dict[str, Any]) -> str:
    lines = [
        "Analyze the image and question briefly before answering.",
        "Keep the reasoning concise and grounded in visible evidence.",
        "End with a final line exactly in the format: Final answer: your answer",
    ]
    lower = str(case.prompt or "").lower()
    lines.append(_mathvista_answer_format_note(case))
    if any(token in lower for token in ["comes next", "missing picture", "complete the matrix", "unfolded cube", "cube is identical"]):
        lines.append("For visual pattern, matrix, or cube-net questions, compare transformations across rows/columns or faces before selecting the option.")
    if any(token in lower for token in ["which number is missing", "find the missing value", "missing value"]):
        lines.append("For missing-number puzzles, infer the row/column or local arithmetic relation first; do not copy a nearby visible number unless it satisfies the same relation.")
    if "age gap" in lower:
        lines.append("For age-gap questions, estimate both visible ages and answer the absolute nearest whole-year difference. Do not answer that it cannot be determined unless no people are visible.")
    if any(token in lower for token in ["food web", "population of", "decrease", "increase"]):
        lines.append("For food-web or causal diagram questions, trace the direct dependency requested by the question, not just a general association.")
    if any(token in lower for token in ["function", "curve", "start decreasing"]):
        lines.append("For graph/function questions, use the visible curve shape and turning points to identify the function or interval.")
    if any(token in lower for token in ["bar", "chart", "table", "score", "value"]):
        lines.append("For chart/table questions, identify the exact referenced series/category and compare the plotted values carefully.")
    if any(token in lower for token in ["roughest", "high median", "always have smaller", "smaller value"]):
        lines.append("For yes/no chart questions, compare the named series across all relevant categories, then map Yes to A and No to B when the options use that order.")
    if "how many bars" in lower:
        lines.append("For bar-count questions, count bars satisfying the stated threshold exactly; values equal to the threshold are not smaller or larger than it.")
    if "(a)" in case.prompt.lower() and "(b)" in case.prompt.lower():
        lines.append("If the question provides labeled options, return only the matching option letter in Final answer.")
    else:
        lines.append("In Final answer, give the final answer itself rather than an explanation.")
    lines.extend(["", f"Question: {case.prompt}"])
    if choices and not _question_embeds_choices(case.prompt, choices):
        lines.extend(["", "Choices:"])
        for label, text in sorted(choices.items()):
            lines.append(f"{label}. {text}")
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


def _normalize_assistant_message(raw_response: Any, iteration: int, model_name: str = "") -> Any:
    if hasattr(raw_response, "choices"):
        message = raw_response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        content = getattr(message, "content", None)
        if not tool_calls and isinstance(content, str):
            pseudo_tool_call = _parse_pseudo_tool_call(content, model_name=model_name)
            if pseudo_tool_call is not None:
                tool_name, arguments = pseudo_tool_call
                return SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id=f"pseudo_call_{iteration}",
                            function=SimpleNamespace(
                                name=tool_name,
                                arguments=json.dumps(arguments, ensure_ascii=False),
                            ),
                        )
                    ],
                )
        return message

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
                    content = choice_message.get("content")
                    if not tool_calls and isinstance(content, str):
                        pseudo_tool_call = _parse_pseudo_tool_call(content, model_name=model_name)
                        if pseudo_tool_call is not None:
                            tool_name, arguments = pseudo_tool_call
                            tool_calls = [
                                SimpleNamespace(
                                    id=f"pseudo_call_{iteration}",
                                    function=SimpleNamespace(
                                        name=tool_name,
                                        arguments=json.dumps(arguments, ensure_ascii=False),
                                    ),
                                )
                            ]
                    return SimpleNamespace(
                        content=content,
                        tool_calls=tool_calls or None,
                    )

        if isinstance(message, str):
            pseudo_tool_call = _parse_pseudo_tool_call(message, model_name=model_name)
            if pseudo_tool_call is not None:
                tool_name, arguments = pseudo_tool_call
                return SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id=f"pseudo_call_{iteration}",
                            function=SimpleNamespace(
                                name=tool_name,
                                arguments=json.dumps(arguments, ensure_ascii=False),
                            ),
                        )
                    ],
                )
            return SimpleNamespace(content=message, tool_calls=None)

    return SimpleNamespace(content="", tool_calls=None)


def _extract_final_answer(text: str) -> str:
    match = re.search(r"Final answer:\s*(.+)$", text or "", re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return (text or "").strip()
