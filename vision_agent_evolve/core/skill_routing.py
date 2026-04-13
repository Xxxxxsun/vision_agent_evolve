"""Skill resolution and prompt assembly for function-calling runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from skills import Skill, discover_skills

from .types import TaskCase


@dataclass
class ResolvedSkillContext:
    """Resolved hierarchical skill package for one task case."""

    matched_skills: list[Skill] = field(default_factory=list)
    foundation_skills: list[Skill] = field(default_factory=list)
    all_skills: list[Skill] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    prompt_blocks: list[str] = field(default_factory=list)
    routing_notes: list[str] = field(default_factory=list)
    final_answer_policy: str = ""


class SkillResolver:
    """Resolve task-specific and foundation skills from one or more skill roots."""

    def __init__(self, skill_roots: Iterable[Path] | None = None):
        self.skill_roots = [Path(root) for root in (skill_roots or []) if root]

    def resolve(self, case: TaskCase) -> ResolvedSkillContext:
        skill_pool = self._load_skill_pool()
        if not skill_pool:
            return ResolvedSkillContext()

        matched = self._match_primary_skills(case, skill_pool)
        if not matched:
            return ResolvedSkillContext()
        foundation = [skill for skill in skill_pool.values() if skill.level == "foundation"]
        ordered = self._resolve_dependencies(matched + foundation, skill_pool)
        matched_names = {skill.name for skill in matched}

        tool_names = _merge_names(
            _normalize_tool_names(skill.tool_names)
            for skill in ordered
        )
        prompt_blocks = [_render_skill_block(skill) for skill in ordered]
        routing_notes = [
            f"Match skill `{skill.name}` when: {skill.applicability_conditions}"
            for skill in matched
            if skill.applicability_conditions
        ]
        final_answer_policy = next(
            (skill.final_answer_policy.strip() for skill in matched if skill.final_answer_policy.strip()),
            "",
        )
        return ResolvedSkillContext(
            matched_skills=[skill for skill in ordered if skill.name in matched_names],
            foundation_skills=[skill for skill in ordered if skill.level == "foundation"],
            all_skills=ordered,
            tool_names=tool_names,
            prompt_blocks=[block for block in prompt_blocks if block],
            routing_notes=routing_notes,
            final_answer_policy=final_answer_policy,
        )

    def _load_skill_pool(self) -> dict[str, Skill]:
        skill_map: dict[str, Skill] = {}
        for root in self.skill_roots:
            if not root.exists():
                continue
            for skill in discover_skills(root):
                if skill.name not in skill_map:
                    skill_map[skill.name] = skill
        return skill_map

    def _match_primary_skills(self, case: TaskCase, skill_pool: dict[str, Skill]) -> list[Skill]:
        names = _candidate_skill_names(case)
        matched: list[Skill] = []
        for name in names:
            skill = skill_pool.get(name)
            if skill and skill not in matched:
                matched.append(skill)
        return matched

    def _resolve_dependencies(self, roots: list[Skill], skill_pool: dict[str, Skill]) -> list[Skill]:
        ordered: list[Skill] = []
        visiting: set[str] = set()

        def visit(skill: Skill) -> None:
            if skill.name in visiting:
                return
            if skill in ordered:
                return
            visiting.add(skill.name)
            for dep_name in list(skill.depends_on) + list(skill.children):
                dep = skill_pool.get(dep_name)
                if dep is not None:
                    visit(dep)
            visiting.remove(skill.name)
            ordered.append(skill)

        for skill in roots:
            visit(skill)
        return ordered


def resolve_skill_roots(capability_root: Path | None, static_skills_dir: Path | None) -> list[Path]:
    """Return skill roots in precedence order."""
    roots: list[Path] = []
    if capability_root is not None:
        cap_root = Path(capability_root)
        if (cap_root / "skills").exists():
            roots.append(cap_root / "skills")
        elif cap_root.exists():
            roots.append(cap_root)
    if static_skills_dir is not None:
        roots.append(Path(static_skills_dir))
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _candidate_skill_names(case: TaskCase) -> list[str]:
    names: list[str] = []
    metadata = case.metadata if isinstance(case.metadata, dict) else {}
    explicit = metadata.get("skill_names")
    if isinstance(explicit, (list, tuple)):
        for item in explicit:
            value = str(item).strip()
            if value and value not in names:
                names.append(value)
    explicit_one = str(metadata.get("skill_name", "")).strip()
    if explicit_one and explicit_one not in names:
        names.append(explicit_one)

    for value in [case.capability_family(), case.dataset_name(), case.problem_id]:
        value = str(value).strip()
        if value and value not in names:
            names.append(value)

    family = case.capability_family()
    parts = [part for part in str(family).split("_") if part]
    for size in range(len(parts) - 1, 0, -1):
        candidate = "_".join(parts[:size])
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _normalize_tool_names(tool_names: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in tool_names:
        value = str(item).strip()
        if not value:
            continue
        if value.startswith("tool:"):
            value = value.split(":", 1)[1].strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def _merge_names(groups: Iterable[list[str]]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item and item not in merged:
                merged.append(item)
    return merged


def _render_skill_block(skill: Skill) -> str:
    title = skill.description.strip() or skill.name
    lines = [f"### {skill.name}", title]
    if skill.applicability_conditions:
        lines.append(f"Applicability: {skill.applicability_conditions}")
    if skill.tool_names:
        lines.append(f"Preferred tools: {', '.join(_normalize_tool_names(skill.tool_names))}")
    if skill.children:
        lines.append(f"Child skills: {', '.join(skill.children)}")
    content_lines = [line.rstrip() for line in skill.content.strip().splitlines() if line.strip()]
    for line in content_lines[:12]:
        lines.append(line)
    return "\n".join(lines).strip()
