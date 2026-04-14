---
name: vstar_relative_position
description: "SOP for VStar spatial relation questions (left/right/above/below)"
level: mid
depends_on: ["vstar"]
tool_names: ["list_images", "get_image_info", "zoom_image"]
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks whether one named object is on the left/right/above/below of another."
---

# VStar Relative Position

## Trigger
- The question compares the spatial relation (left/right/above/below) between two named objects.
- The critical requirement is preserving the global reference frame (viewer's perspective on the full image).

## Procedure
1. Identify both named objects in the original full image.
2. If one or both objects are too small to locate confidently, use `zoom_image` with the estimated position of that object:
   - Set `center_x` and `center_y` to where that object appears in the scene (normalized [0.0, 1.0]).
   - Use a moderate factor (2–3) to avoid losing too much of the surrounding context.
3. After localizing both objects, return to reasoning about the **full image** reference frame.
4. Judge the spatial relation from the viewer's perspective (not the object's own orientation).
5. Map the semantic relation to the matching option letter.
6. Return the option letter only.

## Tool Hints
- Use `zoom_image` only to confirm the location of a hard-to-find object, not to replace the global frame.
- After zooming, use the localized position information to reason about left/right in the full image.
- Never use a zoomed patch as the final reference for the spatial judgment.

## Failure Checks
- Do not infer left/right from the object's own facing direction or body orientation.
- Do not let a zoomed local patch override the full-scene spatial relationship.
- Do not answer with the word `left`, `right`, `above`, or `below` directly — return the matching option letter.
- Keep the original full-image perspective as the ground truth for all spatial judgments.
