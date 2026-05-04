---
name: mathvista
description: "Minimal MathVista skill — zoom to read, python to compute"
level: mid
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
applicability_conditions: "Use for MathVista visual math questions."
---

# MathVista

Tools are available by default. Use them proactively:
1. If any value in the figure is small or hard to read → call `zoom_image` (factor 2–4) on that region.
2. For all non-trivial arithmetic → call `execute_python` with `print()` for the result.
3. For MCQ → return the matching option letter only. For free-form → return the number or short text directly.

Do not use tools for pure visual pattern matching ("comes next", IQ matrix), yes/no MCQ, or simple object counts.
Do not include units, formulas, or alternatives in the final answer line.
