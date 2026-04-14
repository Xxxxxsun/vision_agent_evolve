# Function-Calling Skills

`function_calling_vqa` now supports hierarchical prompt-routing skills without enabling self-evolution.
The runtime currently supports skill-aware function-calling on:

- `vstar`
- `chartqa`
- `mathvista`
- `hrbench`

## Where skills are loaded from

- Static skills: repo `skills/`
- Optional capability root: `--capability-root <path>`
  - If `<path>/skills` exists, that directory is used
  - Otherwise `<path>` itself is treated as the skill root

Capability-root skills override static skills with the same `name`.

## Skill matching

For each case, the runtime tries to match skills by:

1. `metadata.skill_names`
2. `metadata.skill_name`
3. `case.capability_family()`
4. `case.dataset_name()`
5. `case.problem_id`
6. Prefixes of `capability_family` such as `vstar` for `vstar_direct_attributes`

If no family skill matches, no skills are injected into the function-calling prompt.

If a family skill matches, foundation skills are included automatically.

## Supported frontmatter

```md
---
name: vstar_direct_attributes
description: "Route small-object attribute questions to zoom-first reasoning"
level: mid
depends_on: ["vision_analysis"]
children: ["zoom_focus"]
tool_names: ["zoom_image", "list_images"]
routing_mode: soft
final_answer_policy: option_letter
applicability_conditions: "Use when the task asks about color or material of a small object."
---
```

Supported fields:

- `name`
- `description`
- `level`
- `depends_on`
- `children`
- `tool_names`
- `routing_mode`
- `final_answer_policy`
- `applicability_conditions`

## Runtime behavior

- Skills are rendered into a compact `Skill Context` block inside the user prompt
- `references/*.md` are expanded into compact branch-detail blocks
- `tool_names` now means preferred tools, not a hard whitelist
- The runtime derives `effective_tool_names` by merging preferred tools with a dataset/family fallback tool pool
- Skills are soft guidance only
  - They do not force a tool chain
  - The model still decides whether to call tools
- For selected families, foundation skills are filtered so generic advice such as `try_direct_first` does not conflict with task-specific guidance

The runtime also records debug metadata into `per_case.jsonl`:

- `skill_names`
- `foundation_skill_names`
- `preferred_tool_names`
- `effective_tool_names`
- `tool_schema_names`

## Recommended layout

Use one router skill per family and keep branch details in child skills.

Example:

- `skills/vstar/SKILL.md`
- `skills/vstar_direct_attributes/SKILL.md`
- `skills/vstar_relative_position/SKILL.md`
- `skills/zoom_focus/SKILL.md`

Use `references/...` docs when a skill needs extra branch detail without bloating the main prompt.

The repo now also includes dataset-level skills for:

- `skills/chartqa/SKILL.md`
- `skills/mathvista/SKILL.md`
- `skills/hrbench/SKILL.md`

These are intentionally lightweight:

- `chartqa`
  - emphasizes local chart inspection and optional arithmetic with `execute_python`
- `mathvista`
  - emphasizes visual extraction first, then optional calculation
- `hrbench`
  - emphasizes zoom/crop for tiny local text or symbols, then option selection
