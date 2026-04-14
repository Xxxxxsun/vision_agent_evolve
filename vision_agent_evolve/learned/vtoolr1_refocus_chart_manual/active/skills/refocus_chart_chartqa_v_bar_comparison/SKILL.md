---
name: refocus_chart_chartqa_v_bar_comparison
description: "SOP for vertical-bar comparison questions on Refocus_Chart."
level: mid
depends_on: ["focus_on_x_values_with_draw", "refocus_chart_region_crop"]
applicability_conditions: "Use for vertical-bar questions comparing two or more named categories or checking a boolean relation between them."
---

## SOP
1. Confirm this applies: the chart is vertical and the question compares two or more named categories.
2. Run `python -m tools focus_on_x_values_with_draw <image_path>`.
3. Then run `python -m tools refocus_chart_region_crop <image_path>` with the compared labels and the full `x_values_bbox` JSON mapping.
4. Read the relevant bars from the crop, compute the requested difference or comparison, and avoid relying on memory.
5. For yes/no questions, commit to plain `Yes` or `No`.
6. For numeric comparisons, return only the final number.
