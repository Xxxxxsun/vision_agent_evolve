---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy direct-visual-compare."
level: mid
depends_on: []
applicability_conditions: "when both referenced objects are large, salient, and unambiguous in the image; when their horizontal ordering is obvious without assistance; when tool use would add little beyond straightforward visual comparison"
        ---

## SOP
1. Confirm this applies: when both referenced objects are large, salient, and unambiguous in the image; when their horizontal ordering is obvious without assistance; when tool use would add little beyond straightforward visual comparison
2. If the avoid condition applies (when either object is small, ambiguous, partially occluded, or one of many similar instances; when the model is not confidently localizing both entities from the full image; when prior family failures suggest missing localization rather than reasoning difficulty), answer directly from the raw image.
3. Do not call a tool unless the case clearly matches a stronger family trigger.
4. Answer the original question directly from the raw image.
