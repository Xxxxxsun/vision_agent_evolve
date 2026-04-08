---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy locate_then_compare_positions."
level: mid
depends_on: []
applicability_conditions: "when the question asks whether one named object is left/right or above/below another named object; when both target objects are likely visually identifiable in a generic scene image; when a family-level reusable grounding step is preferred over direct guessing"
        ---

## SOP
1. Confirm this applies: when the question asks whether one named object is left/right or above/below another named object; when both target objects are likely visually identifiable in a generic scene image; when a family-level reusable grounding step is preferred over direct guessing
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the relation asked is depth, distance, overlap, containment, or motion rather than 2D relative position; when the target entities are not concrete visible objects or cannot be localized reliably from their names alone; when the image is too ambiguous and even approximate object localization is unlikely to separate the targets), skip the tool path and answer directly; otherwise answer from the final artifact.
