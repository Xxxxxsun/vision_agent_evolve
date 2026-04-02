---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy generic localized inspection before answering."
level: mid
depends_on: []
applicability_conditions: "Use when the question depends on a small local region but it is unclear in advance whether the needed evidence is text or a visual marker.; Use when the image may contain a scoreboard, logo, uniform patch, or sign that needs closer inspection.; Use when direct reading from the full image is uncertain and a broader local search should precede text-focused reading."
        ---

## SOP
1. Confirm this applies: Use when the question depends on a small local region but it is unclear in advance whether the needed evidence is text or a visual marker.; Use when the image may contain a scoreboard, logo, uniform patch, or sign that needs closer inspection.; Use when direct reading from the full image is uncertain and a broader local search should precede text-focused reading.
2. Run `python -m tools localized_region_zoom <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_text_zoom <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the question is clearly global and answerable from the whole image without local inspection.; Avoid when the task is primarily counting many repeated objects; use a counting aid instead.; Avoid when the target is strictly a color attribute and text is unlikely to matter.), skip the tool path and answer directly; otherwise answer from the final artifact.
