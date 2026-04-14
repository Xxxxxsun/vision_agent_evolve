---
name: chartqa
description: "Router skill for chart reading and lightweight chart arithmetic"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
final_answer_policy: direct_answer
applicability_conditions: "Use for ChartQA questions about values, comparisons, maxima/minima, and short chart text."
---

# ChartQA

## Trigger
- Use for chart reading questions where the answer comes directly from chart values, labels, or a simple calculation.

## Procedure
1. Identify the chart element named in the question.
2. If labels, legends, or bars are small, use `zoom_image` or `crop_image`.
3. Extract only the values needed for the answer.
4. Use `execute_python` only for arithmetic after reading the chart.
5. Return the final numeric value or short text answer directly.

## Tool Hints
- Use `zoom_image` first for crowded labels or legends.
- Use `crop_image` when a chart region must be isolated.
- Use `execute_python` for sums, differences, ratios, or totals.

## Failure Checks
- Do not answer from a nearby bar or line by mistake.
- Keep units and year/category labels aligned with the extracted values.
