---
name: vstar_relative_position_ref
description: "Branch detail for left/right relation questions in VStar"
level: low
---

# Relative Position

## Procedure
1. Identify the two named objects in the original full image.
2. Judge left/right from the viewer's perspective.
3. Determine the semantic relation first, then map it to the matching option letter.
4. Return only the option letter in the final answer.

## Tool Policy
- Default: do not use visual tools.
- Use a visual tool only if one of the named objects is too small to localize at all.
- If a visual tool is needed, keep the full-scene left/right frame in mind; never let the zoomed local view replace the original frame.

## Failure Checks
- Do not infer left/right from the object's own facing direction.
- Do not switch reference frames after zooming.
- Do not answer with the word `left` or `right`; return the matching option letter.
