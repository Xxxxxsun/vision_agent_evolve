---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy zoom_after_localization."
level: mid
depends_on: []
applicability_conditions: "when the target object is likely small, distant, or hard to distinguish at full-image scale; when localization alone may find the object but not expose enough detail for reliable color judgment; when the scene contains many items and a magnified local view would improve attribute reading"
        ---

## SOP
1. Confirm this applies: when the target object is likely small, distant, or hard to distinguish at full-image scale; when localization alone may find the object but not expose enough detail for reliable color judgment; when the scene contains many items and a magnified local view would improve attribute reading
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the object is already large and visually clear; when the task requires only scene-level understanding rather than localized evidence; when the question asks about text or count rather than a visible object attribute), skip the tool path and answer directly; otherwise answer from the final artifact.
