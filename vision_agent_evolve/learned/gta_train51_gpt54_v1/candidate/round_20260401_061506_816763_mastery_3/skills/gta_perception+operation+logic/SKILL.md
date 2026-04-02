---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy direct_read_if_large_clear."
level: mid
depends_on: []
applicability_conditions: "When the nutrition values and serving basis are already large and legible in the image without magnification; When the task only needs straightforward arithmetic after an obvious label read"
        ---

## SOP
1. Confirm this applies: When the nutrition values and serving basis are already large and legible in the image without magnification; When the task only needs straightforward arithmetic after an obvious label read
2. If the avoid condition applies (When text is small, dense, or ambiguous; When multiple candidate labels exist and localization is needed to avoid reading the wrong value), answer directly from the raw image.
3. Do not call a tool unless the case clearly matches a stronger family trigger.
4. Answer the original question directly from the raw image.
