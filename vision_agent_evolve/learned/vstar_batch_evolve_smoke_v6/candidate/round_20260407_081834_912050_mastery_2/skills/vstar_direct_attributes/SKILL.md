---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_focused_local_inspection."
level: mid
depends_on: []
applicability_conditions: "when the task is a direct local color question and the main risk is missing the discriminative color evidence; when multiple nearby objects or clutter make raw inspection unreliable; when the target object may be small or partially occluded but still visually identifiable"
        ---

## SOP
1. Confirm this applies: when the task is a direct local color question and the main risk is missing the discriminative color evidence; when multiple nearby objects or clutter make raw inspection unreliable; when the target object may be small or partially occluded but still visually identifiable
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the question is not about color or another short visible attribute; when the target depends on reading text labels rather than appearance; when there is no clearly localized object mention in the question), skip the tool path and answer directly; otherwise answer from the final artifact.
