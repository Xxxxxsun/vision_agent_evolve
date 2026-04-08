---
name: vstar_relative_position
description: "Route left/right object-relation questions to either direct localization or a scene-grounded localization chain, then compare horizontal positions before answering."
level: mid
depends_on: []
applicability_conditions: "Applies to image questions asking whether one named object is on the left or right of another named object in the image plane, especially when object naming may need disambiguation; do not use the scene-grounding chain when both objects are already visually obvious and directly localizable."
        ---

## Router
1. Confirm the task is a simple image-plane left/right comparison between two named visible objects.
2. If object names may have synonyms, the scene is cluttered, or brief scene grounding would help identify the entities, follow [references/tool_branch.md](references/tool_branch.md).
3. If the two queried objects are visually obvious, uniquely identifiable, and speed/compactness matters, follow [references/no_tool_branch.md](references/no_tool_branch.md).
4. Do not answer from language priors; in all branches, explicitly identify both objects and compare their horizontal positions.
5. Return only the left/right answer mapped to the provided choices.
