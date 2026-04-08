---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy locate-then-compare-position."
level: mid
depends_on: []
applicability_conditions: "Use for image-plane relation questions asking whether one named object is left/right or above/below another.; Use when both target objects are visually identifiable entities and the task only requires comparing their approximate centers or vertical/horizontal extents."
        ---

## SOP
1. Confirm this applies: Use for image-plane relation questions asking whether one named object is left/right or above/below another.; Use when both target objects are visually identifiable entities and the task only requires comparing their approximate centers or vertical/horizontal extents.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (Do not use when the question requires reading text, counting instances, or reasoning about depth/front-behind.; Avoid when either object name is too vague to localize reliably or when more than two reference relations must be compared.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
