---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy direct_visual_compare_no_tool."
level: mid
depends_on: []
applicability_conditions: "when both referenced objects are large, salient, and easy to distinguish at a glance; when the image is simple enough that the relative position can be judged confidently without auxiliary tooling; when using tools would add little value over immediate image-grounded comparison"
        ---

## SOP
1. Confirm this applies: when both referenced objects are large, salient, and easy to distinguish at a glance; when the image is simple enough that the relative position can be judged confidently without auxiliary tooling; when using tools would add little value over immediate image-grounded comparison
2. If the avoid condition applies (when previous failures suggest missed grounding from not using a tool; when objects are small, crowded, partially occluded, or visually similar to nearby distractors; when confidence is low about which instances of the named objects are intended), answer directly from the raw image.
3. Do not call a tool unless the case clearly matches a stronger family trigger.
4. Answer the original question directly from the raw image.
