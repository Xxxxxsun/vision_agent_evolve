"""Simplified capability storage."""

from __future__ import annotations
import json
import shutil
from pathlib import Path
from datetime import datetime

from skills import load_skill
from .types import ToolProposal, SkillProposal, ValidationResult


class CapabilityStore:
    """Store and manage learned capabilities."""

    def __init__(self, learned_dir: Path):
        self.learned_dir = learned_dir
        self.tools_dir = learned_dir / "tools"
        self.skills_dir = learned_dir / "skills"
        self.snapshots_dir = learned_dir.parent / "snapshots"
        self.log_file = learned_dir / "evolution_log.jsonl"

        # Create directories
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def promote_tool(self, proposal: ToolProposal, validation: ValidationResult):
        """Promote tool to learned capabilities."""
        tool_file = self.tools_dir / f"{proposal.name}.py"
        manifest_file = self.tools_dir / f"{proposal.name}.json"
        tool_tmp = self.tools_dir / f".{proposal.name}.py.tmp"
        manifest_tmp = self.tools_dir / f".{proposal.name}.json.tmp"

        # Write both source and manifest before promotion is considered committed.
        tool_tmp.write_text(proposal.code, encoding="utf-8")

        # Save metadata
        manifest = {
            "name": proposal.name,
            "description": proposal.description,
            "applicability_conditions": proposal.applicability_conditions,
            "usage_example": proposal.usage_example,
            "created_at": datetime.now().isoformat(),
            "validation": {
                "static_ok": validation.static_ok,
                "origin_ok": validation.origin_ok,
                "regression_ok": validation.regression_ok,
                "leakage_detected": validation.leakage_detected,
            },
        }

        manifest_tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tool_tmp.replace(tool_file)
        manifest_tmp.replace(manifest_file)

        self._log_promotion("tool", proposal.name, "keep")

    def remove_tool(self, tool_name: str):
        """Remove a staged tool and its metadata."""
        (self.tools_dir / f"{tool_name}.py").unlink(missing_ok=True)
        (self.tools_dir / f"{tool_name}.json").unlink(missing_ok=True)

    def promote_skill(self, problem_id: str, proposal: SkillProposal):
        """Promote the current task-family skill by overwriting its short rule set."""
        skill_dir = self.skills_dir / problem_id
        skill_dir.mkdir(exist_ok=True)

        skill_file = skill_dir / "SKILL.md"
        rendered = f"""---
name: {problem_id}
description: "{proposal.description}"
level: {proposal.level}
depends_on: {json.dumps(proposal.depends_on)}
applicability_conditions: "{proposal.applicability_conditions}"
---

{proposal.content}
"""
        skill_file.write_text(rendered)

        self._log_promotion("skill", problem_id, "keep")

    def save_failure_skill(self, problem_id: str, case_id: str, proposal: SkillProposal):
        """Persist a failure-derived lesson without promoting it as the main solver skill."""
        failure_dir = self.skills_dir / problem_id / "failure_skills"
        failure_dir.mkdir(parents=True, exist_ok=True)

        skill_file = failure_dir / f"case_{case_id}.md"
        rendered = f"""---
name: {problem_id}_case_{case_id}_failure_lesson
description: "{proposal.description}"
level: {proposal.level}
depends_on: {json.dumps(proposal.depends_on)}
applicability_conditions: "{proposal.applicability_conditions}"
kind: failure_lesson
---

{proposal.content}
"""
        skill_file.write_text(rendered)
        self._log_promotion("failure_skill", f"{problem_id}:case_{case_id}", "keep")

    def snapshot_current_capabilities(self, snapshot_name: str) -> Path:
        """Copy the current learned subset to a stable snapshot directory."""
        target = self.snapshots_dir / snapshot_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.learned_dir, target)
        return target

    def has_skill(self, problem_id: str) -> bool:
        """Return whether a task-family skill exists."""
        return (self.skills_dir / problem_id / "SKILL.md").exists()

    def get_skill(self, problem_id: str):
        """Load the current task-family skill if it exists."""
        skill_file = self.skills_dir / problem_id / "SKILL.md"
        if not skill_file.exists():
            return None
        return load_skill(skill_file)

    def list_failure_skills(self, problem_id: str, limit: int = 3):
        """Load the most recent reusable failure lessons for a task family."""
        failure_dir = self.skills_dir / problem_id / "failure_skills"
        if not failure_dir.exists():
            return []

        lessons = []
        for skill_file in sorted(
            failure_dir.glob("case_*.md"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            try:
                lesson = load_skill(skill_file)
            except Exception:
                continue
            if lesson.kind != "failure_lesson":
                continue
            if not lesson.content.strip():
                continue
            lessons.append(lesson)
            if len(lessons) >= limit:
                break
        return lessons

    def list_capabilities(self) -> list[str]:
        """List all learned capabilities."""
        caps = []

        # List tools
        for tool_file in self.tools_dir.glob("*.py"):
            caps.append(f"tool:{tool_file.stem}")

        # List skills
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                caps.append(f"skill:{skill_dir.name}")

        return caps

    def get_solved_cases(self) -> list[str]:
        """Get list of case IDs that have been solved."""
        solved = []

        if self.log_file.exists():
            for line in self.log_file.read_text().splitlines():
                try:
                    entry = json.loads(line)
                    if entry.get("solve_success"):
                        solved.append(entry.get("case_id", ""))
                except json.JSONDecodeError:
                    pass

        return [c for c in solved if c]

    def log_step(self, step_data: dict):
        """Log evolution step."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(step_data) + "\n")

    def _log_promotion(self, cap_type: str, name: str, decision: str):
        """Log capability promotion."""
        entry = {"type": "promotion", "cap_type": cap_type, "name": name, "decision": decision, "timestamp": datetime.now().isoformat()}

        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
