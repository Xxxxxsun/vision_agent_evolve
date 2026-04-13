---
name: vstar_relative_position
description: "SOP for VStar left/right relation questions"
level: mid
depends_on: ["vstar"]
tool_names: []
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks whether one named object is on the left or right side of another."
---

# VStar Relative Position

## Trigger
- The question compares the left/right relation of two named objects.
- The critical requirement is preserving the global reference frame.

## Procedure
1. Identify both named objects in the full image.
2. Judge the semantic relation from the viewer's perspective.
3. Map that semantic relation to the matching option letter.
4. Return the option letter only.

## Tool Hints
- Default to no visual tools.
- Only consider a tool if an object cannot be localized at all in the original image.
- If a local inspection is used, keep the full image as the final left/right reference.

## Failure Checks
- Do not infer left/right from object orientation.
- Do not answer directly with `left` or `right`.
- Do not let a zoomed local patch override the full-scene relation.
