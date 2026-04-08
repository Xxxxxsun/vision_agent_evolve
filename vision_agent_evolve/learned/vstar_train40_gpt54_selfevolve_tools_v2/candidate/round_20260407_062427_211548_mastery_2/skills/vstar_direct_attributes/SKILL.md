---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_focus_then_direct_choice."
level: mid
depends_on: []
applicability_conditions: "Use when the task is a multiple-choice color question about a local object and the image likely contains enough visual evidence without precise detection; Use when the target may be small and benefits from focused color highlighting; Use when quick local evidence extraction is preferable to a stricter detect-then-describe chain"
        ---

## SOP
1. Confirm this applies: Use when the task is a multiple-choice color question about a local object and the image likely contains enough visual evidence without precise detection; Use when the target may be small and benefits from focused color highlighting; Use when quick local evidence extraction is preferable to a stricter detect-then-describe chain
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (Avoid when multiple similar candidate objects make object identity uncertain; Avoid when the question depends on exact object localization before color can be read safely; Avoid when the answer depends on text, counting, or relationships between objects), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
