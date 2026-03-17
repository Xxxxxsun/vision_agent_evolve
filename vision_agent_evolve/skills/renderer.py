"""Skill renderer for system prompts."""

from __future__ import annotations
from .base import Skill


def render_skills(skills: list[Skill]) -> str:
    """Render the active task SOP plus reusable failure lessons."""
    if not skills:
        return ""

    sorted_skills = _resolve_dependencies(skills)
    failure_skills = [skill for skill in sorted_skills if skill.kind == "failure_lesson"]
    normal_skills = [skill for skill in sorted_skills if skill.kind != "failure_lesson"]
    task_skills = [skill for skill in normal_skills if skill.level != "foundation"]
    active_skills = task_skills or normal_skills

    lines: list[str] = []
    if active_skills:
        lines.extend(
            [
                "## Current Task SOP",
                "",
                "Do not output `ACTION: TASK_COMPLETE` before you have executed the required SOP steps and produced a final answer.",
                "",
                "Follow these steps for this solve.",
                "",
            ]
        )

        for skill in active_skills:
            lines.extend(_render_task_skill(skill))
            lines.append("")

    if failure_skills:
        lines.extend(
            [
                "## Failure Lessons / Things To Watch",
                "",
                "Use these as reusable warnings and verification hints for this task family.",
                "",
            ]
        )
        for skill in failure_skills:
            lines.extend(_render_failure_skill(skill))
            lines.append("")

    return "\n".join(lines).rstrip()


def _resolve_dependencies(skills: list[Skill]) -> list[Skill]:
    """Resolve skill dependencies and return in dependency order."""
    # Build dependency graph
    skill_map = {s.name: s for s in skills}
    resolved = []
    visiting = set()

    def visit(skill: Skill):
        if skill.name in visiting:
            # Circular dependency, skip
            return
        if skill in resolved:
            return

        visiting.add(skill.name)

        # Visit dependencies first
        for dep_name in skill.depends_on:
            dep = skill_map.get(dep_name)
            if dep:
                visit(dep)

        visiting.remove(skill.name)
        resolved.append(skill)

    # Visit all skills
    for skill in skills:
        visit(skill)

    return resolved


def _render_task_skill(skill: Skill) -> list[str]:
    """Render a task-specific skill as the active rule for this solve."""
    lines = [
        f"### {skill.name}",
        "",
        skill.description,
    ]
    if skill.applicability_conditions:
        lines.extend(["", f"Applicability: {skill.applicability_conditions}"])
    lines.extend(["", skill.content.strip()])
    return lines


def _render_failure_skill(skill: Skill) -> list[str]:
    """Render a reusable failure lesson separately from the main SOP."""
    title = skill.description or skill.name
    lines = [f"### {title}"]
    if skill.applicability_conditions:
        lines.extend(["", f"When this matters: {skill.applicability_conditions}"])
    lines.extend(["", skill.content.strip()])
    return lines
