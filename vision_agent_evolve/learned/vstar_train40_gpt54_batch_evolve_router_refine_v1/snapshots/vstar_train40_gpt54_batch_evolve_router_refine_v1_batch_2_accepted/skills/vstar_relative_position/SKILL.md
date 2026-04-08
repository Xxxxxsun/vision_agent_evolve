---
name: vstar_relative_position
description: "Route simple natural-image left/right object-comparison questions either to a no-tool direct comparison when both referents are easy to localize or to an ImageDescription -> TextToBbox -> relative_position_marker branch when scene context is needed to disambiguate the objects before comparing horizontal position."
level: mid
depends_on: []
applicability_conditions: "Applies to multiple-choice or direct questions asking whether one visible named object is on the left or right side of another in a natural image, where the required relation is simple horizontal ordering; use the tool branch when object names are broad, unusual, visually confusable, or there are multiple candidate instances and scene context can help identify the intended pair; do not use this SOP for tasks needing 3D/viewpoint reasoning, heavy occlusion resolution, non-horizontal relations, or when clutter makes caption-style scene summary unlikely to help."
        ---

## Router
1. Verify the task is a simple left/right comparison between two visible named objects in a natural image.
2. If both queried objects are already straightforward to localize and compare directly, use the no-tool branch in `references/no_tool_branch.md`.
3. If object names may be broad, unusual, visually confusable, or there are multiple candidate instances and brief scene context can disambiguate them, use `references/tool_branch.md`.
4. Do not use the tool branch when the scene is too cluttered for caption-style context to resolve referents, or when the task is not a simple horizontal left/right relation.
5. After branching, answer only by the horizontal ordering of the referenced objects.
