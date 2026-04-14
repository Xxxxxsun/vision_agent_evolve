---
name: mathvista
description: "Router skill for visual math questions with local inspection and optional calculation"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
applicability_conditions: "Use for MathVista free-form and multiple-choice visual reasoning questions."
---

# MathVista

## Trigger
- Use for questions that require extracting visual quantities, reading geometry or diagrams, and optionally doing arithmetic.

## Procedure
1. Identify the relevant visual entities or quantities from the image.
2. Use `zoom_image` or `crop_image` if text, ticks, or geometric details are hard to inspect.
3. If arithmetic is needed, compute it with `execute_python`.
4. If the question is multiple choice, map the result to the matching option letter.
5. Otherwise return the direct final answer.

## Tool Hints
- Prefer `zoom_image` for small annotations or crowded diagrams.
- Prefer `execute_python` once the numeric inputs are extracted.

## Failure Checks
- Do not mix visual estimation with exact arithmetic when the figure provides exact values.
- Re-check units, precision, and option mapping before the final answer.
