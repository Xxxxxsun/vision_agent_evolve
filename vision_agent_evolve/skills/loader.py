"""Skill loader and discovery."""

from __future__ import annotations
import re
from pathlib import Path
from typing import Literal

from .base import Skill


def load_skill(skill_path: Path) -> Skill:
    """Load a skill from markdown file."""
    content = skill_path.read_text(encoding="utf-8")

    # Parse frontmatter
    metadata = _parse_frontmatter(content)
    main_content = _strip_frontmatter(content)

    # Find references
    references, missing_references = _resolve_references(skill_path, main_content)

    return Skill(
        name=metadata.get("name", skill_path.stem),
        description=metadata.get("description", ""),
        content=main_content,
        kind=metadata.get("kind", "skill"),
        level=metadata.get("level", "mid"),
        depends_on=metadata.get("depends_on", []),
        children=metadata.get("children", []),
        tool_names=metadata.get("tool_names", []),
        routing_mode=metadata.get("routing_mode", "soft"),
        final_answer_policy=metadata.get("final_answer_policy", ""),
        applicability_conditions=metadata.get("applicability_conditions", ""),
        skill_path=skill_path,
        references=references,
        missing_references=missing_references,
    )


def discover_skills(skills_dir: Path) -> list[Skill]:
    """Discover all skills in directory."""
    if not skills_dir.exists():
        return []

    skills = []
    for skill_file in skills_dir.rglob("*.md"):
        # Skip reference files
        if "references" in skill_file.parts:
            continue

        try:
            skill = load_skill(skill_file)
            skills.append(skill)
        except Exception as e:
            print(f"Warning: Failed to load skill {skill_file}: {e}")

    return skills


def select_skills(
    skills: list[Skill],
    task_type: str | None = None,
    level: Literal["foundation", "high", "mid", "low"] | None = None,
) -> list[Skill]:
    """Select relevant skills based on task type and level."""
    selected = skills

    # Filter by task type
    if task_type:
        key = task_type.lower()
        selected = [
            s for s in selected
            if key in s.name.lower() or key in str(s.skill_path).lower()
        ]

    # Filter by level
    if level:
        selected = [s for s in selected if s.level == level]

    # Always include foundation skills
    foundation = [s for s in skills if s.level == "foundation"]
    selected = foundation + [s for s in selected if s not in foundation]

    return selected


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from markdown."""
    if not content.startswith("---\n"):
        return {}

    end_idx = content.find("\n---", 4)
    if end_idx == -1:
        return {}

    block = content[4:end_idx]
    metadata = {}

    for line in block.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"\'')

        # Handle list values
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                value = []
            else:
                value = [v.strip().strip('"\'') for v in inner.split(",") if v.strip()]

        metadata[key] = value

    return metadata


def _strip_frontmatter(content: str) -> str:
    """Remove frontmatter from markdown."""
    if not content.startswith("---\n"):
        return content

    end_idx = content.find("\n---", 4)
    if end_idx == -1:
        return content

    return content[end_idx + 4:].lstrip("\n")


def _resolve_references(skill_path: Path, content: str) -> tuple[list[Path], list[str]]:
    """Resolve only explicitly referenced branch docs."""
    references: list[Path] = []
    missing: list[str] = []
    seen: set[str] = set()
    for target in _extract_reference_targets(content):
        if target in seen:
            continue
        seen.add(target)
        ref_path = (skill_path.parent / target).resolve()
        try:
            ref_path.relative_to(skill_path.parent.resolve())
        except ValueError:
            missing.append(target)
            continue
        if ref_path.exists() and ref_path.is_file():
            references.append(ref_path)
        else:
            missing.append(target)
    return references, missing


def _extract_reference_targets(content: str) -> list[str]:
    """Return referenced branch-doc paths in order of appearance."""
    pattern = re.compile(r"(?P<path>references/[A-Za-z0-9._/\-]+\.md)")
    return [match.group("path") for match in pattern.finditer(content)]
