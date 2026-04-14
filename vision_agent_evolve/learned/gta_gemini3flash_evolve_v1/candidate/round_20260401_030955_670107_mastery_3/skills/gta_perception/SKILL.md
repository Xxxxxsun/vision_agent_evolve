---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy Direct Visual Reasoning."
level: mid
depends_on: []
applicability_conditions: "The sports event and teams are globally famous and identifiable by iconic colors or stadium architecture; The question is a general scene classification task without local dependencies"
        ---

## SOP
1. Confirm this applies: The sports event and teams are globally famous and identifiable by iconic colors or stadium architecture; The question is a general scene classification task without local dependencies
2. If the avoid condition applies (The question asks for specific, non-obvious names that require reading small labels; The image contains multiple teams or complex overlapping text), answer directly from the raw image.
3. Do not call a tool unless the case clearly matches a stronger family trigger.
4. Answer the original question directly from the raw image.
