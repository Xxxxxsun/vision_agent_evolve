"""Skill resolution and prompt assembly for function-calling runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from skills import Skill, discover_skills
from skills.loader import load_skill

from .types import TaskCase


@dataclass
class ResolvedSkillContext:
    """Resolved hierarchical skill package for one task case."""

    matched_skills: list[Skill] = field(default_factory=list)
    foundation_skills: list[Skill] = field(default_factory=list)
    all_skills: list[Skill] = field(default_factory=list)
    preferred_tool_names: list[str] = field(default_factory=list)
    effective_tool_names: list[str] = field(default_factory=list)
    prompt_blocks: list[str] = field(default_factory=list)
    reference_blocks: list[str] = field(default_factory=list)
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

        foundation = self._select_foundation_skills(case, skill_pool)
        allowed_foundations = {skill.name for skill in foundation}
        matched_ordered = self._resolve_dependencies(matched, skill_pool, allowed_foundations)
        foundation_ordered = self._resolve_dependencies(foundation, skill_pool, allowed_foundations)
        ordered = _dedupe_skills(matched_ordered + foundation_ordered)

        preferred_tool_names = _merge_names(
            _normalize_tool_names(skill.tool_names)
            for skill in matched_ordered
        )
        effective_tool_names = _merge_names(
            [
                preferred_tool_names,
                _family_fallback_tool_pool(case),
            ]
        )
        reference_blocks = _collect_reference_blocks(matched_ordered)
        prompt_blocks = []
        prompt_blocks.extend(_render_skill_block(skill) for skill in matched_ordered)
        prompt_blocks.extend(reference_blocks)
        prompt_blocks.extend(_render_foundation_skill_block(skill) for skill in foundation_ordered)
        routing_notes = [
            f"Task-specific skill guidance overrides generic foundation advice for this case."
        ]
        routing_notes.extend(
            f"Match skill `{skill.name}` when: {skill.applicability_conditions}"
            for skill in matched_ordered
            if skill.applicability_conditions
        )
        final_answer_policy = next(
            (skill.final_answer_policy.strip() for skill in matched_ordered if skill.final_answer_policy.strip()),
            "",
        )
        return ResolvedSkillContext(
            matched_skills=matched,
            foundation_skills=foundation_ordered,
            all_skills=ordered,
            preferred_tool_names=preferred_tool_names,
            effective_tool_names=effective_tool_names,
            prompt_blocks=[block for block in prompt_blocks if block],
            reference_blocks=reference_blocks,
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
        pruned: list[Skill] = []
        matched_names = {skill.name for skill in matched}
        for skill in matched:
            is_parent_router = any(
                other != skill.name and other.startswith(f"{skill.name}_")
                for other in matched_names
            )
            if is_parent_router:
                continue
            pruned.append(skill)
        return pruned

    def _select_foundation_skills(self, case: TaskCase, skill_pool: dict[str, Skill]) -> list[Skill]:
        family = case.capability_family().strip().lower()
        foundation = [skill for skill in skill_pool.values() if skill.level == "foundation"]
        selected: list[Skill] = []
        for skill in foundation:
            if family in {
                "vstar_direct_attributes",
                "vstar_relative_position",
                "chartqa",
                "mathvista_generic_multi_choice",
                "mathvista_generic_free_form",
                "hrbench_single",
                "hrbench_cross",
            } and skill.name == "try_direct_first":
                continue
            selected.append(skill)
        return selected

    def _resolve_dependencies(
        self,
        roots: list[Skill],
        skill_pool: dict[str, Skill],
        allowed_foundations: set[str],
    ) -> list[Skill]:
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
                    if dep.level == "foundation" and dep.name not in allowed_foundations:
                        continue
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


def _dedupe_skills(skills: list[Skill]) -> list[Skill]:
    ordered: list[Skill] = []
    seen: set[str] = set()
    for skill in skills:
        if skill.name in seen:
            continue
        seen.add(skill.name)
        ordered.append(skill)
    return ordered


def _render_skill_block(skill: Skill) -> str:
    title = skill.description.strip() or skill.name
    lines = [f"### Skill: {skill.name}", title]
    if skill.applicability_conditions:
        lines.append(f"Applicability: {skill.applicability_conditions}")
    if skill.tool_names:
        lines.append(f"Preferred tools: {', '.join(_normalize_tool_names(skill.tool_names))}")
    content_lines = [line.rstrip() for line in skill.content.strip().splitlines() if line.strip()]
    for line in content_lines[:12]:
        lines.append(line)
    return "\n".join(lines).strip()


def _render_foundation_skill_block(skill: Skill) -> str:
    title = skill.description.strip() or skill.name
    lines = [f"### Foundation: {skill.name}", title]
    content_lines = [line.rstrip() for line in skill.content.strip().splitlines() if line.strip()]
    for line in content_lines[:8]:
        lines.append(line)
    return "\n".join(lines).strip()


def _collect_reference_blocks(skills: list[Skill]) -> list[str]:
    blocks: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        for ref_path in skill.references:
            key = str(ref_path.resolve()) if ref_path.exists() else str(ref_path)
            if key in seen:
                continue
            seen.add(key)
            try:
                ref_skill = load_skill(ref_path)
            except Exception:
                continue
            blocks.append(_render_reference_block(ref_skill))
    return [block for block in blocks if block]


def _render_reference_block(skill: Skill) -> str:
    title = skill.description.strip() or skill.name
    lines = [f"### Branch Detail: {title}"]
    if skill.applicability_conditions:
        lines.append(f"Applicability: {skill.applicability_conditions}")
    if skill.tool_names:
        lines.append(f"Preferred tools: {', '.join(_normalize_tool_names(skill.tool_names))}")
    content_lines = [line.rstrip() for line in skill.content.strip().splitlines() if line.strip()]
    for line in content_lines[:12]:
        lines.append(line)
    return "\n".join(lines).strip()


def _family_fallback_tool_pool(case: TaskCase) -> list[str]:
    family = case.capability_family().strip().lower()
    dataset_name = str(case.metadata.get("dataset_name", "") or "").strip().lower()
    if family == "vstar_direct_attributes":
        return ["list_images", "get_image_info", "zoom_image", "crop_image"]
    if family == "vstar_relative_position":
        return ["list_images", "get_image_info"]
    if dataset_name == "chartqa":
        return ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
    if dataset_name == "mathvista":
        return ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
    if dataset_name == "hrbench":
        return ["list_images", "get_image_info", "zoom_image", "crop_image"]
    return []
