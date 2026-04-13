---
name: vstar
description: "Router skill for VStar multiple-choice visual questions"
level: mid
depends_on: ["vision_analysis", "reasoning", "try_direct_first"]
applicability_conditions: "Use for VStar benchmark questions with small-object attributes or pairwise left/right relations."
---

# VStar Router

## Trigger
- Use this router for VStar benchmark cases.
- First identify whether the question is about:
  - a local object attribute such as color or material, or
  - a pairwise left/right relation between two named objects.

## Routing Rule
1. If the question asks for color, material, or another local visual attribute of one object, follow `vstar_direct_attributes`.
2. If the question asks whether one named object is on the left or right side of another, follow `vstar_relative_position`.
3. If the case does not clearly match either branch, reason directly from the full image and answer with the option letter.

## General Policy
- Treat VStar as a multiple-choice benchmark. The final answer should be the matching option letter.
- Keep reasoning short and tied to visible evidence.
- Prefer the full image as the default reference frame.
- Only use tools when they remove a specific source of uncertainty.

## Branch Notes
- For attribute cases, `zoom_image` should be the default first tool whenever the target is not already large and unmistakable.
- For relative-position cases, preserving the global frame matters more than local enlargement.

See branch detail:
- `references/direct_attributes.md`
- `references/relative_position.md`
