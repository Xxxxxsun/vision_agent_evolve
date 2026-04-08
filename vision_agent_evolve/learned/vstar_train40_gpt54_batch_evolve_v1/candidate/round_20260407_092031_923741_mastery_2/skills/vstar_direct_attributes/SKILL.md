---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_evidence_zoom."
level: mid
depends_on: []
applicability_conditions: "when the task is a localized color lookup and the object is visible but occupies only a small region; when multiple answer choices are basic colors and the main challenge is extracting local color evidence; when a family-level reusable color-focused inspection step is preferred over generic scene description"
        ---

## SOP
1. Confirm this applies: when the task is a localized color lookup and the object is visible but occupies only a small region; when multiple answer choices are basic colors and the main challenge is extracting local color evidence; when a family-level reusable color-focused inspection step is preferred over generic scene description
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the question is not about color; when the object category itself is unclear and must first be found by name; when the whole object is already prominent and direct inspection is sufficient), skip the tool path and answer directly; otherwise answer from the final artifact.
