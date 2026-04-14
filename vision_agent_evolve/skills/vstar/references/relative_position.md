---
name: vstar_relative_position_ref
description: "Branch detail for spatial relation questions in VStar"
level: low
---

# Relative Position

## Procedure
1. Identify the two named objects in the original full image.
2. If an object is too small to locate, use `zoom_image` at its estimated position (center_x, center_y in [0,1]).
3. Use the localization result to note *where* the object sits in the full image — do not use the zoomed patch as the new reference frame.
4. Judge left/right (or above/below) from the viewer's perspective using the full scene.
5. Map the semantic relation to the matching option letter.
6. Return only the option letter.

## Tool Policy
- Use `zoom_image` only to localize an object that is too small to find by eye.
- Set center_x/center_y to where the object is estimated to be in the full image.
- After zooming to localize, always reason about the spatial relation in the full-image coordinate frame.
- Never let the zoomed view change your frame of reference for left/right.

## Failure Checks
- Do not infer left/right from the object's own facing direction.
- Do not let a zoomed patch replace the original full-image frame.
- Do not answer with the word `left`, `right`, `above`, or `below` directly — return the option letter.
