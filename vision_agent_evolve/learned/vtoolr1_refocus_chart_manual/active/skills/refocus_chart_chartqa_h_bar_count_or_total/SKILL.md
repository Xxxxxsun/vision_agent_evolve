---
name: refocus_chart_chartqa_h_bar_count_or_total
description: "SOP for horizontal-bar counting and aggregation questions on Refocus_Chart."
level: mid
depends_on: ["focus_on_y_values_with_draw", "refocus_chart_region_crop"]
applicability_conditions: "Use for horizontal-bar questions asking for counts, sums, totals, or yes/no comparisons involving named categories."
---

## SOP
1. Confirm this applies: the chart is horizontal and the task is counting bars/categories or aggregating named categories.
2. If the question asks how many bars, categories, or food items are shown, count the available y-axis labels directly from metadata rather than guessing from the raw image.
3. If the question asks for a sum, difference, or boolean comparison involving named categories, run `python -m tools focus_on_y_values_with_draw <image_path>`.
4. Then run `python -m tools refocus_chart_region_crop <image_path>` with the named target labels and the full `y_values_bbox` JSON mapping so the relevant rows are isolated.
5. Compute the requested total, difference, or comparison carefully and answer with only the final numeric value or yes/no.
6. Do not add explanation once you have the answer.
