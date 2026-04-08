---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy direct_visual_read."
level: mid
depends_on: []
applicability_conditions: "Use when the referenced object is large, unambiguous, and its color is plainly visible at normal scale.; Use when the image contains only one plausible target matching the question and no fine-grained localization is needed.; Use when tool use would likely add latency without improving reliability."
        ---

## SOP
1. Confirm this applies: Use when the referenced object is large, unambiguous, and its color is plainly visible at normal scale.; Use when the image contains only one plausible target matching the question and no fine-grained localization is needed.; Use when tool use would likely add latency without improving reliability.
2. If the avoid condition applies (Do not use when the target is small, off-center, partially hidden, or surrounded by visually similar items.; Do not use when prior failures in the cluster suggest missed localized inspection for color attributes.; Do not use when the scene is cluttered enough that the noun phrase could map to several candidates.), answer directly from the raw image.
3. Do not call a tool unless the case clearly matches a stronger family trigger.
4. Answer the original question directly from the raw image.
