"""Base skill definitions."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class Skill:
    """A skill document that guides agent behavior."""

    name: str
    description: str
    content: str
    kind: str = "skill"
    level: Literal["foundation", "high", "mid", "low"] = "mid"
    depends_on: list[str] = field(default_factory=list)
    applicability_conditions: str = ""
    skill_path: Path | None = None
    references: list[Path] = field(default_factory=list)

    def __str__(self) -> str:
        """Format skill for system prompt."""
        lines = [f"### Skill: {self.name}", "", self.description]
        if self.applicability_conditions:
            lines.extend(["", f"Applicability: {self.applicability_conditions}"])
        lines.extend(["", self.content])
        return "\n".join(lines)
