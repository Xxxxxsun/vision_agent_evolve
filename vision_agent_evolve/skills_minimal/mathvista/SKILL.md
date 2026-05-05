---
name: mathvista
description: "Minimal MathVista skill — read image directly, python for arithmetic only"
level: mid
tool_names: ["execute_python"]
applicability_conditions: "Use for MathVista visual math questions."
---

# MathVista

Read values **directly from the original image** — do not zoom or crop.
Call `execute_python` (with `print()`) only to verify arithmetic after extracting values from the image.
For MCQ: return the matching option letter. For free-form: return the number or short text directly.
Do not use Python for visual counting, pattern matching, or yes/no questions — answer those directly.
