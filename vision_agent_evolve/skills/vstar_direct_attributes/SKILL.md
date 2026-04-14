---
name: vstar_direct_attributes
description: "SOP for VStar local attribute questions (color, material, shape)"
level: mid
depends_on: ["vstar"]
tool_names: ["list_images", "get_image_info", "zoom_image"]
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks about color, material, or another local visual attribute of one named object."
---

# VStar Direct Attributes

## Trigger
- The question asks what color, material, or visual attribute a named object has.
- The challenge is that the target object is often small, off-center, or mixed with similar objects.

## Procedure
1. Read the question and identify the exact named target object.
2. Scan the original image and estimate where the target object is located (which quadrant or region).
3. Call `zoom_image` with:
   - `factor`: 2–4 (higher for very small objects)
   - `center_x`: estimated horizontal position as a fraction [0.0, 1.0] — 0.0 is the left edge, 1.0 is the right edge
   - `center_y`: estimated vertical position as a fraction [0.0, 1.0] — 0.0 is the top edge, 1.0 is the bottom edge
   - Example: target in upper-right area → `center_x=0.75, center_y=0.25`
   - Example: target in lower-left area → `center_x=0.25, center_y=0.75`
4. Inspect the zoomed view and confirm you are looking at the correct object.
   - If the target is not visible in the zoomed patch, adjust center_x/center_y and zoom again.
5. Compare the visible attribute against the answer options.
6. Return the matching option letter.

## Tool Hints
- Always call `zoom_image` unless the target is unambiguously large in the original image.
- Set center_x and center_y based on where the target appears in the scene — do not leave them at 0.5 if the target is off-center.
- Use factor=2 for moderate zoom, factor=3–4 for very small or distant targets.
- Use `get_image_info` first if you need the image dimensions to calibrate your estimate.

## Failure Checks
- Do not zoom to the center (0.5, 0.5) if the target object is clearly off-center — this is the most common mistake.
- Do not switch to a nearby object that happens to be easier to see.
- Do not answer with a free-form color description; return the option letter only.
- If two zoom attempts still leave the attribute ambiguous, choose the option best supported across original and zoomed views together.
