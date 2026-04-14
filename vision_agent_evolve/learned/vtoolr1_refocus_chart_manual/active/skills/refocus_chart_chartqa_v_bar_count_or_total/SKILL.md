---
name: refocus_chart_chartqa_v_bar_count_or_total
description: "SOP for vertical-bar counting and aggregation questions on Refocus_Chart."
level: mid
depends_on: ["focus_on_x_values_with_draw", "refocus_chart_region_crop"]
applicability_conditions: "Use for vertical-bar questions asking for counts, sums, totals, or yes/no comparisons involving named categories."
---

## SOP
1. Confirm this applies: the chart is vertical and the task is counting bars/categories or aggregating named categories.
2. If the question asks how many bars or categories are shown, count the available x-axis labels directly from metadata.
3. If the question asks for a sum, difference, or boolean comparison involving named categories, run `python -m tools focus_on_x_values_with_draw <image_path>`.
4. Then run `python -m tools refocus_chart_region_crop <image_path>` with the named target labels and the `x_values_bbox` JSON mapping.
5. Compute the requested total or comparison carefully and answer with only the final numeric value or yes/no.
6. Do not add explanation once you have the answer.
