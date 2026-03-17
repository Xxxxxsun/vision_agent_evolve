"""Core data types for Vision Agent Evolve."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
from enum import Enum


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class TaskCase:
    """A single task/puzzle to solve."""
    case_id: str
    problem_id: str
    prompt: str
    gold_answer: str
    image_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def dense_caption(self) -> str:
        """Return the optional dense caption for this case."""
        return str(self.metadata.get("dense_caption", "")).strip()


@dataclass
class Message:
    """Chat message."""
    role: Literal["system", "user", "assistant"]
    content: str | list[dict[str, Any]]


@dataclass
class AgentAction:
    """Parsed action from agent."""
    name: str
    arguments: dict[str, Any]


@dataclass
class AgentStep:
    """Single step in agent execution."""
    turn: int
    thought: str | None = None
    action: AgentAction | None = None
    observation: str | None = None
    artifacts: list[str] = field(default_factory=list)  # Generated files (images, etc)
    is_final: bool = False
    is_format_error: bool = False


@dataclass
class AgentResult:
    """Result of agent execution."""
    task: str
    final_answer: str
    steps: list[AgentStep]
    total_turns: int
    success: bool
    error: str | None = None
    messages: list[Message] = field(default_factory=list)
    all_artifacts: list[str] = field(default_factory=list)  # All artifacts from all steps

    def get_image_artifacts(self) -> list[str]:
        """Get only image artifacts (png, jpg, jpeg)."""
        image_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        return [
            art for art in self.all_artifacts
            if any(art.lower().endswith(ext) for ext in image_exts)
        ]


@dataclass
class ToolResult:
    """Standardized tool execution result."""
    status: Literal["ok", "error"]
    answer: str
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None
    debug_info: str = ""

    def __str__(self) -> str:
        """Format as agent-readable output."""
        lines = [f"STATUS: {self.status}"]
        if self.answer:
            lines.insert(0, f"ANSWER: {self.answer}")
        if self.artifacts:
            lines.append(f"ARTIFACTS: {', '.join(self.artifacts)}")
        if self.status == "error" and self.error:
            lines.append("---")
            lines.append(f"ERROR: {self.error}")
        elif self.debug_info:
            lines.append("---")
            lines.append(self.debug_info)
        return "\n".join(lines)
