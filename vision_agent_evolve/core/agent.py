"""ReAct agent for vision tasks."""

from __future__ import annotations
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .types import AgentResult, AgentStep, Message
from .parser import ReActParser
from .vlm_client import VLMClient, ModelSettings


SYSTEM_TEMPLATE = """You are a command-line vision agent.

You solve vision tasks by iterating: Thought -> Action -> Observation.

You only have access to these tools:
{tool_definitions}

Action format (strict):
Action:
{{
  "name": "bash",
  "arguments": {{"command": "..."}}
}}

Rules:
- Follow the current task SOP exactly.
- If the SOP includes an exact tool command, execute that command before answering from the original image alone.
- Do not output ACTION: TASK_COMPLETE until you have finished the SOP steps, or there is no actionable step left.
- Use bash to run CLI tools for processing.
- Never output raw shell commands outside Action JSON.
- Wait for Observation after each Action.
- When done, output exactly these two lines:
  Final Answer: <your answer>
  ACTION: TASK_COMPLETE

{extra_instructions}
"""


@dataclass
class AgentConfig:
    """Agent configuration."""
    max_turns: int = 20
    verbose: bool = False
    work_dir: Path | None = None
    required_tool_name: str | None = None
    required_skill_name: str | None = None
    require_bash_action_before_complete: bool = False
    required_image_artifact_before_complete: bool = False
    learned_dir: Path | None = None
    allowed_tool_names: list[str] | None = None
    require_python_tool_command: bool = False


class ReActAgent:
    """ReAct agent with vision support."""

    def __init__(
        self,
        client: VLMClient,
        config: AgentConfig | None = None,
        tool_definitions: str = "",
        extra_instructions: str = "",
    ):
        self.client = client
        self.config = config or AgentConfig()
        self.parser = ReActParser()
        self.system_prompt = SYSTEM_TEMPLATE.format(
            tool_definitions=tool_definitions,
            extra_instructions=extra_instructions,
        )
        self.project_root = Path(__file__).resolve().parents[1]
        configured_work_dir = self.config.work_dir or Path("artifacts")
        if configured_work_dir.is_absolute():
            self.work_dir = configured_work_dir
        else:
            self.work_dir = self.project_root / configured_work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        task: str,
        image_path: str = "",
        initial_observations: list[tuple[str, list[str]]] | None = None,
    ) -> AgentResult:
        """Run agent on task."""
        self._current_image_path = image_path
        self._latest_artifact_path = ""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._user_content(f"Task: {task}", image_path)},
        ]

        for observation, artifacts in initial_observations or []:
            messages.append({"role": "user", "content": self._build_observation_content(observation, artifacts)})

        steps: list[AgentStep] = []
        required_tool_used = self.config.required_tool_name is None
        required_skill_used = not (
            self.config.required_skill_name or self.config.require_bash_action_before_complete
        )
        required_image_artifact_seen = not self.config.required_image_artifact_before_complete

        for turn in range(1, self.config.max_turns + 1):
            # Get LLM response
            response, _ = self.client.chat(messages, ModelSettings(max_tokens=12000))  # Ignore usage in agent
            parse_result = self.parser.parse_response(response)
            step = AgentStep(turn=turn, thought=response)

            # Task complete
            if parse_result.is_task_complete:
                if not required_tool_used:
                    required_command = f"python -m tools {self.config.required_tool_name} <image_path>"
                    warning = (
                        "Current task rule not completed yet. "
                        f"Before giving a final answer, call the validated tool using: {required_command}"
                    )
                    step.is_format_error = True
                    step.observation = warning
                    steps.append(step)
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": self.parser.format_observation(warning)})
                    continue
                if not required_skill_used:
                    warning = self._required_skill_warning()
                    step.is_format_error = True
                    step.observation = warning
                    steps.append(step)
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": self.parser.format_observation(warning)})
                    continue
                if not required_image_artifact_seen:
                    warning = self._required_artifact_warning()
                    step.is_format_error = True
                    step.observation = warning
                    steps.append(step)
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": self.parser.format_observation(warning)})
                    continue

                step.is_final = True
                steps.append(step)
                final = self.parser.extract_final_answer(response)
                messages.append({"role": "assistant", "content": response})

                # Collect all artifacts
                all_artifacts = []
                for s in steps:
                    all_artifacts.extend(s.artifacts)

                return AgentResult(
                    task=task,
                    final_answer=final,
                    steps=steps,
                    total_turns=turn,
                    success=True,
                    messages=[Message(**m) for m in messages],
                    all_artifacts=all_artifacts,
                )

            # Format error
            if parse_result.is_format_error:
                step.is_format_error = True
                step.observation = parse_result.error_message
                steps.append(step)
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": self.parser.format_observation(parse_result.error_message or ""),
                })
                continue

            # Execute action
            assert parse_result.action is not None
            action = parse_result.action
            step.action = action

            if action.name != "bash":
                observation = f"Error: unknown tool '{action.name}'. Only 'bash' is allowed."
            else:
                command = str(action.arguments.get("command", ""))
                if self._uses_required_tool(command):
                    required_tool_used = True
                if self._uses_required_skill(command):
                    required_skill_used = True
                observation = self._run_bash(command)

            step.observation = observation

            # Extract artifacts from observation (look for ARTIFACTS: line)
            step.artifacts = self._normalize_artifacts(self._extract_artifacts(observation))
            if any(Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"} for path in step.artifacts):
                required_image_artifact_seen = True
            if step.artifacts:
                self._latest_artifact_path = step.artifacts[-1]
            steps.append(step)

            messages.append({"role": "assistant", "content": response})
            # Build observation message - include image artifacts as visual content if present
            obs_content = self._build_observation_content(observation, step.artifacts)
            messages.append({"role": "user", "content": obs_content})

        # Max turns exceeded
        all_artifacts = []
        for s in steps:
            all_artifacts.extend(s.artifacts)

        return AgentResult(
            task=task,
            final_answer="",
            steps=steps,
            total_turns=self.config.max_turns,
            success=False,
            error="Max turns exceeded",
            messages=[Message(**m) for m in messages],
            all_artifacts=all_artifacts,
        )

    def _run_bash(self, command: str) -> str:
        """Execute bash command and return output."""
        try:
            command_error = self._validate_command(command)
            if command_error:
                return command_error
            env = os.environ.copy()
            env["VISION_AGENT_PROJECT_ROOT"] = str(self.project_root)
            env["VISION_AGENT_WORK_DIR"] = str(self.work_dir)
            if self.config.learned_dir is not None:
                env["VISION_AGENT_LEARNED_DIR"] = str(self.config.learned_dir)
            rewritten_command = self._rewrite_tool_command(command)
            result = subprocess.run(
                rewritten_command,
                shell=True,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            return output if output else f"Command executed (exit code: {result.returncode})"
        except subprocess.TimeoutExpired:
            return "Error: Command timeout (60s)"
        except Exception as e:
            return f"Error: {e}"

    def _validate_command(self, command: str) -> str | None:
        """Validate whether a shell command respects runtime tool restrictions."""
        stripped = str(command).strip()
        if not stripped:
            return "Error: empty bash command."

        if self.config.require_python_tool_command and not re.search(r"^\s*python(?:3)?\s+-m\s+tools(?:\s|$)", stripped):
            return (
                "Error: this task only allows tool invocations via "
                "'python -m tools <tool_name> ...'."
            )

        allowed_tools = self.config.allowed_tool_names
        if not allowed_tools:
            return None

        match = re.search(r"^\s*python(?:3)?\s+-m\s+tools\s+([A-Za-z0-9_]+)(?:\s|$)", stripped)
        if match is None:
            return (
                "Error: this task only allows approved tool commands via "
                "'python -m tools <tool_name> ...'."
            )

        tool_name = match.group(1)
        if tool_name not in set(allowed_tools):
            allowed_text = ", ".join(allowed_tools)
            return (
                f"Error: tool '{tool_name}' is not allowed for this task. "
                f"Allowed tools: {allowed_text}"
            )
        return None

    def _uses_required_tool(self, command: str) -> bool:
        """Check whether a bash command invokes the required learned tool."""
        if not self.config.required_tool_name:
            return False
        pattern = rf"\bpython3?\s+-m\s+tools\s+{re.escape(self.config.required_tool_name)}(?:\s|$)"
        return re.search(pattern, command) is not None

    def _uses_required_skill(self, command: str) -> bool:
        """Check whether a command satisfies the required skill gate."""
        if self.config.required_tool_name and self._uses_required_tool(command):
            return True
        if self.config.required_skill_name or self.config.require_bash_action_before_complete:
            return bool(command.strip())
        return False

    def _required_skill_warning(self) -> str:
        """Return a user-facing warning when a required skill step was skipped."""
        skill_name = self.config.required_skill_name or "the required task skill"
        return (
            "Current task rule not completed yet. "
            f"Before giving a final answer, execute at least one bash step required by skill '{skill_name}', "
            "observe the result, and then answer."
        )

    def _required_artifact_warning(self) -> str:
        """Return a warning when a required edited artifact was not produced."""
        skill_name = self.config.required_skill_name or "the required task skill"
        return (
            "Current task rule not completed yet. "
            f"Skill '{skill_name}' must produce a new image artifact before you answer. "
            "Run a bash/Python editing step that writes an edited image under artifacts/, wait for the Observation, and then answer."
        )

    def _rewrite_tool_command(self, command: str) -> str:
        """Route learned tool commands through the current Python interpreter."""
        pattern = re.compile(r"^(\s*)python3?\s+-m\s+tools(?=\s|$)")
        match = pattern.match(command)
        rewritten_command = command
        if match:
            prefix = match.group(1)
            rewritten = f"{prefix}{shlex.quote(sys.executable)} -m tools"
            rewritten_command = pattern.sub(rewritten, rewritten_command, count=1)

        current_image = getattr(self, "_current_image_path", "")
        if current_image:
            quoted_current_image = shlex.quote(current_image)
            rewritten_command = rewritten_command.replace('image="<image_path>"', f"image={quoted_current_image}")
            rewritten_command = re.sub(
                r"\binput_file_0\.(?:png|jpg|jpeg|webp|gif)\b",
                quoted_current_image,
                rewritten_command,
            )
            rewritten_command = rewritten_command.replace("<image_path>", quoted_current_image)

        latest_artifact = getattr(self, "_latest_artifact_path", "")
        if latest_artifact:
            quoted_artifact = shlex.quote(latest_artifact)
            rewritten_command = rewritten_command.replace('image="<artifact_path>"', f"image={quoted_artifact}")
            rewritten_command = rewritten_command.replace("<artifact_path>", quoted_artifact)
        return rewritten_command

    def _user_content(self, text: str, image_path: str) -> Any:
        """Create user message content."""
        if image_path:
            return VLMClient.image_message_parts(str(self._resolve_path(image_path)), text)
        return text

    def _build_observation_content(self, observation: str, artifacts: list[str]) -> Any:
        """Build observation message content, embedding image artifacts as visual input."""
        text_content = self.parser.format_observation(observation)

        # Filter to valid image files
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        image_paths = [
            p for p in artifacts
            if Path(p).suffix.lower() in image_exts and self._resolve_existing_path(p) is not None
        ]

        if not image_paths:
            return text_content

        parts: list[dict[str, Any]] = [{"type": "text", "text": text_content}]
        for img_path in image_paths[:3]:  # cap at 3 to avoid token explosion
            try:
                resolved = self._resolve_existing_path(img_path)
                if resolved is None:
                    continue
                parts.append({"type": "text", "text": f"\n[Tool output image: {resolved.name}]"})
                parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(resolved)}})
            except Exception:
                # If image can't be read, skip silently - text observation is still there
                pass

        return parts

    def _extract_artifacts(self, observation: str) -> list[str]:
        """Extract artifact file paths from observation text."""
        # Look for "ARTIFACTS: file1.png, file2.jpg" pattern
        import re
        match = re.search(r'ARTIFACTS:\s*(.+)', observation)
        if match:
            artifacts_str = match.group(1).strip()
            # Split by comma and clean up
            artifacts = [a.strip() for a in artifacts_str.split(',')]
            return artifacts
        return []

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve a path against the project root first, then the work directory."""
        path = Path(path_str)
        if path.is_absolute():
            return path

        project_candidate = self.project_root / path
        if project_candidate.exists():
            return project_candidate

        work_candidate = self.work_dir / path
        if work_candidate.exists():
            return work_candidate

        return project_candidate

    def _resolve_existing_path(self, path_str: str) -> Path | None:
        """Resolve a path only if it exists."""
        path = Path(path_str)
        if path.is_absolute():
            return path if path.exists() else None

        candidates = [
            self.project_root / path,
            self.work_dir / path,
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def _normalize_artifacts(self, artifacts: list[str]) -> list[str]:
        """Normalize artifact paths so later turns can resolve them consistently."""
        normalized: list[str] = []

        for artifact in artifacts:
            resolved = self._resolve_existing_path(artifact)
            if resolved is None:
                normalized.append(artifact)
                continue

            try:
                normalized.append(str(resolved.relative_to(self.project_root)))
            except ValueError:
                normalized.append(str(resolved))

        return normalized
