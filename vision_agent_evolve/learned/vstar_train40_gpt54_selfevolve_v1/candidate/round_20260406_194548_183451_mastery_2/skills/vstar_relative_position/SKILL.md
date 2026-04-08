---
name: vstar_relative_position
description: "Route simple two-object image-plane relative position questions to either direct visual comparison or an ImageDescription→TextToBbox grounding branch when object identity is ambiguous before answering above/below or left/right."
level: mid
depends_on: []
applicability_conditions: "Applies to natural-image multiple-choice questions asking whether one named object is above/below or left/right of another in the image plane; use the grounding branch when object names are ambiguous, uncommon, visually confusable, or direct localization is uncertain; do not use for counting, reading text, depth/front-behind reasoning, comparing more than one relation type, or when the image layout cannot be resolved from the two referenced objects."
        ---

## Router
1. Confirm the task is a two-object image-plane relation question within family scope: above/below or left/right only.
2. If both referenced objects are obvious and easily identifiable, use the direct visual comparison branch in `references/no_tool_branch.md`.
3. If either object name is ambiguous, uncommon, easy to confuse, or you are uncertain what is present, use the grounding branch in `references/tool_branch.md`.
4. Do not answer from world knowledge or object priors; use only the observed image arrangement.
5. If the task falls outside supported image-plane relation scope, do not use this SOP.
