---
name: vstar
description: "Router skill for VStar visual questions — no tools"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: []
applicability_conditions: "Use for VStar benchmark questions about local object attributes or pairwise spatial relations."
---

# VStar Router — No Tools

## Routing Rule
1. If the question asks about the color, material, or local visual attribute of one named object → follow `vstar_direct_attributes`.
2. If the question asks whether one named object is left/right/above/below another → follow `vstar_relative_position`.
3. Otherwise → reason directly from the image and return the option letter.

## General Policy
- Return only the option letter as the final answer.
- Keep reasoning short and tied to directly visible evidence.
- The target objects in VStar are often small or off-center — look carefully at the whole image before answering.
