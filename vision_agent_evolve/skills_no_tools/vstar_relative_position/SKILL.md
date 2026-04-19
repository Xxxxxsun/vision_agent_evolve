---
name: vstar_relative_position
description: "Spatial reasoning SOP for VStar relation questions — no tools"
level: mid
depends_on: ["vstar"]
tool_names: []
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks whether one named object is on the left/right/above/below of another."
---

# VStar Relative Position — Spatial Reasoning

## Trigger
- The question asks about the spatial relation (left/right/above/below) between two named objects.

## Procedure
1. Locate both named objects in the full image. Scan carefully — either object may be small or off-center.
2. Establish the reference frame: use the viewer's perspective (your left = image left, your right = image right).
3. Compare the horizontal positions (for left/right) or vertical positions (for above/below) of the two objects.
4. State the spatial relation clearly in your reasoning: "Object A is to the LEFT of Object B."
5. Map that conclusion to the matching option letter.
6. Return only the option letter.

## Spatial Reasoning Rules
- **Left/right**: compare the horizontal center-of-mass of each object. The one with smaller x-coordinate (further left in the image) is on the left.
- **Above/below**: compare vertical position. The one higher in the image (smaller y-coordinate from the top) is above.
- Do NOT use the object's own facing direction to determine left/right — always use the viewer's frame.
- Do NOT let the size or prominence of an object influence the spatial judgment.

## Failure Checks
- Do not infer left/right from which way the object is facing — a car facing right can still be on the left side of the scene.
- Do not answer with the word "left" or "right" directly — return the option letter only.
- If both objects are in roughly the same horizontal position, use their body centers for the comparison, not their extremities.
