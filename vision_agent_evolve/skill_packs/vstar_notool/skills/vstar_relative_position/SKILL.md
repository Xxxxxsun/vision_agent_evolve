---
name: vstar_relative_position
description: "Lightweight no-tool guidance for VStar left/right questions"
level: low
depends_on: []
tool_names: []
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks whether one named object is on the left or right side of another."
---

# VStar Relative Position No-Tool

## Procedure
1. Identify both named objects in the full image.
2. Judge left/right from the viewer's perspective.
3. Map that conclusion to the matching option letter.
4. Return the option letter.

## Failure Checks
- Do not infer left/right from object orientation.
- Use the full image as the reference frame.
