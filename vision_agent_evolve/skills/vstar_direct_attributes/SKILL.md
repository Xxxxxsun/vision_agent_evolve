---
name: vstar_direct_attributes
description: "SOP for VStar local attribute questions"
level: mid
depends_on: ["vstar"]
tool_names: ["list_images", "get_image_info", "zoom_image"]
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks about color, material, or another local visual attribute of one object."
---

# VStar Direct Attributes

## Trigger
- The question asks what color or material a named object has.
- The main uncertainty is visual inspection of one local target.

## Procedure
1. Locate the named target in the original image.
2. Unless the target is already large and unmistakable, use `zoom_image`.
3. Keep the target identity fixed across all views.
4. Compare the visible evidence against the answer options.
5. Return the matching option letter.

## Tool Hints
- Default to `zoom_image` for local attribute questions.
- Use `zoom_image` for small, distant, partially occluded, or color-ambiguous targets.
- Use `list_images` or `get_image_info` only as support utilities.
- Do not use `crop_image` by default; start with `zoom_image`.

## Failure Checks
- Avoid switching from the named object to a nearby distractor.
- Avoid free-form color descriptions in the final answer.
- If evidence is mixed, prefer the option best supported across both original and zoomed views.
