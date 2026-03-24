"""Simplified capability storage."""

from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

from skills import load_skill
from .types import CapabilityBundleProposal, FailedDirection, FailureAnalysis, ToolProposal, SkillProposal, ValidationResult


class CapabilityStore:
    """Store and manage learned capabilities."""

    def __init__(self, learned_dir: Path):
        self.learned_dir = learned_dir
        self.tools_dir = learned_dir / "tools"
        self.skills_dir = learned_dir / "skills"
        self.snapshots_dir = learned_dir.parent / "snapshots"
        self.candidates_dir = learned_dir.parent / "candidate"
        self.rejected_plans_file = learned_dir.parent / "rejected_plans.json"
        self.log_file = learned_dir / "evolution_log.jsonl"

        # Create directories
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

    FAILED_DIRECTION_DEDUPE_THRESHOLD = 0.84
    FAILED_DIRECTION_MATCH_THRESHOLD = 0.62

    def promote_tool(self, proposal: ToolProposal, validation: ValidationResult):
        """Promote tool to learned capabilities."""
        self._write_tool(proposal, validation, log_decision=True)

    def _write_tool(self, proposal: ToolProposal, validation: ValidationResult, log_decision: bool) -> None:
        """Write a tool into this capability root."""
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

        if log_decision:
            self._log_promotion("tool", proposal.name, "keep")

    def remove_tool(self, tool_name: str):
        """Remove a staged tool and its metadata."""
        (self.tools_dir / f"{tool_name}.py").unlink(missing_ok=True)
        (self.tools_dir / f"{tool_name}.json").unlink(missing_ok=True)

    def promote_skill(self, problem_id: str, proposal: SkillProposal):
        """Promote the current task-family skill by overwriting its short rule set."""
        self._write_skill(problem_id, proposal, log_decision=True)

    def _write_skill(self, problem_id: str, proposal: SkillProposal, log_decision: bool) -> None:
        """Write a skill into this capability root."""
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
        skill_file.write_text(rendered, encoding="utf-8")

        if log_decision:
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

    def stage_bundle(self, bundle: CapabilityBundleProposal) -> Path:
        """Create a candidate capability root for one planner proposal."""
        candidate_dir = self.candidates_dir / bundle.run_id
        if candidate_dir.exists():
            shutil.rmtree(candidate_dir)
        if self.learned_dir.exists():
            shutil.copytree(self.learned_dir, candidate_dir)
        else:
            candidate_dir.mkdir(parents=True, exist_ok=True)

        candidate_store = CapabilityStore(candidate_dir)
        validation = ValidationResult(passed=True, static_ok=True, origin_ok=True, regression_ok=True)
        for tool in bundle.tools:
            candidate_store._write_tool(tool, validation, log_decision=False)
        for skill in bundle.skills:
            candidate_store._write_skill(skill.name, skill, log_decision=False)
        candidate_store.log_step(
            {
                "type": "candidate_stage",
                "run_id": bundle.run_id,
                "target_family": bundle.target_family,
                "tool_count": len(bundle.tools),
                "skill_count": len(bundle.skills),
            }
        )
        return candidate_dir

    def evaluate_bundle_snapshot(self, run_id: str) -> Path:
        """Return the staged candidate directory for evaluation."""
        candidate_dir = self.candidates_dir / run_id
        if not candidate_dir.exists():
            raise FileNotFoundError(f"Candidate bundle not found: {candidate_dir}")
        return candidate_dir

    def activate_bundle(self, run_id: str, snapshot_name: str = "") -> Path:
        """Atomically replace the active capability root with an accepted candidate."""
        candidate_dir = self.evaluate_bundle_snapshot(run_id)
        replacement_dir = self.learned_dir.parent / f".active_replace_{run_id}"
        if replacement_dir.exists():
            shutil.rmtree(replacement_dir)
        shutil.copytree(candidate_dir, replacement_dir)
        if self.learned_dir.exists():
            shutil.rmtree(self.learned_dir)
        replacement_dir.replace(self.learned_dir)
        if snapshot_name:
            self.snapshot_current_capabilities(snapshot_name)
        self.discard_bundle(run_id)
        self.log_step({"type": "candidate_activate", "run_id": run_id, "snapshot_name": snapshot_name})
        return self.learned_dir

    def discard_bundle(self, run_id: str) -> None:
        """Remove a rejected or superseded candidate bundle."""
        candidate_dir = self.candidates_dir / run_id
        if candidate_dir.exists():
            shutil.rmtree(candidate_dir)

    def load_active_snapshot(self, snapshot_name: str) -> Path:
        """Restore a snapshot back into the active capability root."""
        snapshot_dir = self.snapshots_dir / snapshot_name
        if not snapshot_dir.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_dir}")
        if self.learned_dir.exists():
            shutil.rmtree(self.learned_dir)
        shutil.copytree(snapshot_dir, self.learned_dir)
        return self.learned_dir

    def record_rejected_plan(self, entry: dict, limit: int = 12) -> None:
        """Append one rejected candidate summary for future planner context."""
        rows = self.list_recent_rejected_plans(limit=limit)
        rows.insert(0, entry)
        self.rejected_plans_file.write_text(
            json.dumps(rows[:limit], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_recent_rejected_plans(self, limit: int = 10) -> list[dict]:
        """Load recent rejected-plan summaries."""
        if not self.rejected_plans_file.exists():
            return []
        try:
            rows = json.loads(self.rejected_plans_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(rows, list):
            return []
        return rows[:limit]

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

    def save_failed_direction(self, problem_id: str, direction: FailedDirection) -> dict:
        """Persist one failed direction, merging near-duplicates in-place."""
        path = self._failed_directions_path(problem_id)
        rows = self._read_failed_directions(path)

        best_index = -1
        best_similarity = 0.0
        for index, row in enumerate(rows):
            candidate = self._coerce_failed_direction(row)
            similarity = self.failed_direction_similarity(candidate, direction)
            same_action = candidate.next_action == direction.next_action
            if same_action and similarity >= self.FAILED_DIRECTION_DEDUPE_THRESHOLD and similarity > best_similarity:
                best_index = index
                best_similarity = similarity

        if best_index >= 0:
            merged = self._coerce_failed_direction(rows[best_index])
            merged.times_failed += 1
            merged.last_failed_at = direction.created_at
            merged.last_case_id = direction.case_id
            merged.last_attempt = direction.attempt
            if direction.retry_answer:
                merged.retry_answer = direction.retry_answer
            if direction.failure_reason:
                merged.failure_reason = direction.failure_reason
            if direction.tool_goal:
                merged.tool_goal = direction.tool_goal
            if direction.skill_update_note:
                merged.skill_update_note = direction.skill_update_note
            if direction.used_tool:
                merged.used_tool = direction.used_tool
            merged.chain_trace = list(direction.chain_trace or merged.chain_trace)
            rows[best_index] = asdict(merged)
            stored = merged
        else:
            if not direction.direction_signature:
                direction.direction_signature = self._direction_signature(direction)
            if not direction.last_failed_at:
                direction.last_failed_at = direction.created_at
            if not direction.last_case_id:
                direction.last_case_id = direction.case_id
            if not direction.last_attempt:
                direction.last_attempt = direction.attempt
            rows.append(asdict(direction))
            stored = direction

        rows.sort(key=lambda row: row.get("last_failed_at") or row.get("created_at") or "", reverse=True)
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        return {
            "stored_direction": asdict(stored),
            "deduped": best_index >= 0,
            "similarity": best_similarity,
        }

    def list_failed_directions(self, problem_id: str, limit: int = 10) -> list[FailedDirection]:
        """Load recent failed directions for one task family."""
        path = self._failed_directions_path(problem_id)
        rows = self._read_failed_directions(path)
        directions = [self._coerce_failed_direction(row) for row in rows]
        directions.sort(key=lambda row: row.last_failed_at or row.created_at, reverse=True)
        return directions[:limit]

    def find_similar_failed_directions(
        self,
        problem_id: str,
        analysis: FailureAnalysis,
        limit: int = 3,
    ) -> list[dict]:
        """Return the closest historical failed directions for one analysis."""
        candidate = FailedDirection(
            case_id="",
            attempt=0,
            created_at="",
            root_cause=analysis.root_cause,
            missing_step=analysis.missing_step,
            next_action=analysis.next_action,
            tool_goal=analysis.tool_goal,
            skill_update_note=analysis.skill_update_note,
        )
        rows: list[dict] = []
        for direction in self.list_failed_directions(problem_id, limit=50):
            similarity = self.failed_direction_similarity(direction, candidate)
            if similarity < self.FAILED_DIRECTION_MATCH_THRESHOLD:
                continue
            rows.append(
                {
                    "case_id": direction.case_id,
                    "attempt": direction.attempt,
                    "next_action": direction.next_action,
                    "missing_step": direction.missing_step,
                    "tool_goal": direction.tool_goal,
                    "skill_update_note": direction.skill_update_note,
                    "failure_reason": direction.failure_reason,
                    "source": direction.source,
                    "times_failed": direction.times_failed,
                    "similarity": round(similarity, 3),
                    "direction_signature": direction.direction_signature,
                }
            )
        rows.sort(key=lambda row: row["similarity"], reverse=True)
        return rows[:limit]

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

    def _failed_directions_path(self, problem_id: str) -> Path:
        failure_dir = self.skills_dir / problem_id
        failure_dir.mkdir(parents=True, exist_ok=True)
        return failure_dir / "failed_directions.json"

    @classmethod
    def failed_direction_similarity(cls, left: FailedDirection, right: FailedDirection) -> float:
        """Heuristic semantic similarity between two failed directions."""
        left_text = cls._semantic_text(left)
        right_text = cls._semantic_text(right)
        ratio = SequenceMatcher(None, left_text, right_text).ratio()

        left_tokens = set(left_text.split())
        right_tokens = set(right_text.split())
        union = left_tokens | right_tokens
        jaccard = (len(left_tokens & right_tokens) / len(union)) if union else 1.0

        action_bonus = 0.08 if left.next_action == right.next_action else 0.0
        return min(1.0, max(ratio, jaccard) + action_bonus)

    @classmethod
    def _semantic_text(cls, direction: FailedDirection) -> str:
        parts = [
            direction.root_cause,
            direction.missing_step,
            direction.next_action,
            direction.tool_goal,
            direction.skill_update_note,
        ]
        return cls._normalize_text(" | ".join(part for part in parts if part))

    @classmethod
    def _direction_signature(cls, direction: FailedDirection) -> str:
        payload = cls._semantic_text(direction)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]

    @staticmethod
    def _normalize_text(text: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
        return " ".join(cleaned.split())

    @staticmethod
    def _read_failed_directions(path: Path) -> list[dict]:
        if not path.exists():
            return []
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return rows if isinstance(rows, list) else []

    @classmethod
    def _coerce_failed_direction(cls, row: dict) -> FailedDirection:
        direction = FailedDirection(
            case_id=str(row.get("case_id", "")),
            attempt=int(row.get("attempt", 0) or 0),
            created_at=str(row.get("created_at", "")),
            root_cause=str(row.get("root_cause", "")),
            missing_step=str(row.get("missing_step", "")),
            next_action=str(row.get("next_action", "give_up")),
            tool_goal=str(row.get("tool_goal", "")),
            skill_update_note=str(row.get("skill_update_note", "")),
            chain_trace=list(row.get("chain_trace", [])),
            used_tool=row.get("used_tool"),
            retry_answer=row.get("retry_answer"),
            failure_reason=str(row.get("failure_reason", "")),
            source=str(row.get("source", "retry_failed")),
            direction_signature=str(row.get("direction_signature", "")),
            times_failed=int(row.get("times_failed", 1) or 1),
            last_failed_at=str(row.get("last_failed_at", "")),
            last_case_id=str(row.get("last_case_id", "")),
            last_attempt=int(row.get("last_attempt", 0) or 0),
        )
        if not direction.direction_signature:
            direction.direction_signature = cls._direction_signature(direction)
        if not direction.last_failed_at:
            direction.last_failed_at = direction.created_at
        if not direction.last_case_id:
            direction.last_case_id = direction.case_id
        if not direction.last_attempt:
            direction.last_attempt = direction.attempt
        return direction
