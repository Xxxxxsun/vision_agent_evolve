---
name: vstar_direct_attributes
description: "Lightweight no-tool guidance for VStar attribute questions"
level: low
depends_on: []
tool_names: []
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks about color, material, or another local visual attribute."
---

# VStar Direct Attributes No-Tool

## Procedure
1. Identify the named object in the original image.
2. Compare the visible attribute against the listed options only.
3. Return the best-supported option letter.

## Failure Checks
- Do not switch to a nearby distractor.
