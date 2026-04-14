---
name: vstar_direct_attributes_ref
description: "Branch detail for small-object attribute questions in VStar"
level: low
---

# Direct Attributes

## Procedure
1. Identify the exact target object named in the question.
2. Estimate where the target appears in the image (which quadrant or region).
3. Call `zoom_image` with `center_x` and `center_y` set to the target's estimated position:
   - upper-left → center_x≈0.25, center_y≈0.25
   - upper-right → center_x≈0.75, center_y≈0.25
   - lower-left → center_x≈0.25, center_y≈0.75
   - lower-right → center_x≈0.75, center_y≈0.75
   - off to one side → adjust accordingly
4. After zooming, confirm you are looking at the correct object.
5. Compare the visible attribute against the answer options and return the matching option letter.

## Tool Hints
- Preferred tools: `list_images`, `zoom_image`, `get_image_info`
- Always set center_x and center_y to the target's actual location — the default (0.5, 0.5) only works if the target is near the image center.
- Use factor=2 for moderate zoom, factor=3–4 for very small or distant targets.
- If the first zoom misses the target, re-estimate the position and zoom again.

## Failure Checks
- Do not zoom to (0.5, 0.5) if the target is off-center — this returns an irrelevant patch and hurts accuracy.
- Do not answer based on a nearby object that is easier to see.
- Do not convert a color judgment into a free-form answer; return the option letter only.
- If two zoom attempts are still ambiguous, fall back to the most defensible option across all views.
