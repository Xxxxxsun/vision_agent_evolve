---
name: mathvista
description: "MathVista concise Python calculation gate"
level: mid
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
applicability_conditions: "Use for MathVista questions that require visual reasoning and may need arithmetic verification after values are read from the image."
---

# MathVista

Use the original image directly by default. Some cases expose only `execute_python`; selected local-visual cases also expose `zoom_image`/`crop_image`.

Default to answering directly when no tool is available. When `execute_python` is available for a MathVista case, first read all required numeric or symbolic inputs from the image/question, then call `execute_python` to verify the final arithmetic before answering.

Good uses: arithmetic after reading visual values, sums/totals, subtraction/remaining-count questions, formulas, statistics, unit conversion, or evaluating numeric/expression answer choices. Always `print()` the result.

Do not use Python to read the image, count objects, infer a visual option, answer yes/no visually, identify people/ages, or handle unclear visual details. If the answer is a direct read-off, simple count, visual pattern choice, or semantic MCQ, answer directly.

When visual tools are available, use them only for small local details: ruler marks, arrows/dials, chart bars/labels, object counts/comparisons, medical width judgments, and diagram measurements. Zoom/crop first, then compute only if arithmetic remains.

For multiple-choice questions: compute or reason first, then return the matching option letter only. For open-ended questions: return the numeric or text answer directly.
