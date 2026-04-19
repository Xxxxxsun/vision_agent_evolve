---
name: chartqa
description: "SOP for chart reading and lightweight chart arithmetic"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
final_answer_policy: direct_answer
applicability_conditions: "Use for ChartQA questions that ask for a numeric value, comparison, maximum/minimum, or short text span from a chart."
---

# ChartQA

## Trigger
- The question asks about a specific value, trend, comparison, maximum, minimum, or total visible in a chart image.
- The answer is a short number or text — not an option letter.

## Procedure
1. Read the question carefully and identify the specific chart element(s) needed: a particular bar, line, slice, legend entry, or axis label.
2. Estimate where that element is located within the image using normalized coordinates (0.0 = left/top, 1.0 = right/bottom):
   - x-axis labels and bottom data: center_y ≈ 0.85–0.95
   - y-axis labels and scale: center_x ≈ 0.05–0.15
   - Top-right legend: center_x ≈ 0.80, center_y ≈ 0.10
   - Chart title: center_y ≈ 0.05
   - Main plot area: center_x ≈ 0.55, center_y ≈ 0.50
3. Use `zoom_image` with the estimated center_x/center_y (factor=2–3) to read labels, tick values, or legend entries that are too small to read reliably at the original scale.
4. If a specific region needs pixel-precise isolation (e.g., separating the legend from the plot), call `get_image_info` to obtain the image dimensions, then use `crop_image` with exact pixel coordinates.
5. Extract all needed numeric values from the zoomed/cropped view.
6. Use `execute_python` for any arithmetic — only after the values are clearly read from the chart.
7. Return the final answer as a number or short text directly (no option letter).

## Tool Hints
- `zoom_image`: first tool for small labels, tick marks, and legends — always set center_x/center_y to the target region, not 0.5.
- `crop_image`: use when you need to isolate a chart subregion (e.g., legend block, x-axis band) more precisely than zoom allows.
- `execute_python`: use for differences, sums, ratios, and percentages. Write the extracted values as variables before computing.
- `get_image_info`: call before `crop_image` to get the pixel dimensions needed for accurate coordinates.

## Failure Checks
- Do not read the wrong bar or line — always confirm the category label matches the question.
- Check axis units (%, thousands, millions) before extracting numbers.
- Do not zoom to center (0.5, 0.5) when the target is a corner element like a legend or axis label.
- Do not estimate values by eye if the number is readable — read it exactly.
- For comparison questions, extract both values before computing the difference.

See branch detail:
- `references/chart_reading.md`
- `references/arithmetic.md`
