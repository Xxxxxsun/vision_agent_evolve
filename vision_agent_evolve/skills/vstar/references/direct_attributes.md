---
name: vstar_direct_attributes_ref
description: "Branch detail for small-object attribute questions in VStar"
level: low
---

# Direct Attributes

## Procedure
1. Identify the exact target object named in the question.
2. Check whether the target is large and visually clear in the original image.
3. If the object is not already large and unmistakable, use `zoom_image` before answering.
4. After zooming, re-check the same object rather than switching to a nearby distractor.
5. Compare only against the provided options and return the matching option letter.

## Tool Hints
- Preferred tools: `list_images`, `zoom_image`, `get_image_info`
- Use `list_images` or `get_image_info` only to confirm image ids and metadata.
- Prefer `zoom_image` over `crop_image` as the first inspection tool.
- For color/material questions, default to one `zoom_image` call unless the object is already obviously visible at the original scale.

## Failure Checks
- Do not answer based on a nearby object that is easier to see.
- Do not convert a color judgment into a free-form answer; return the option letter only.
- If the zoomed view is still ambiguous, fall back to the most defensible option from the original image and the zoomed view together.
