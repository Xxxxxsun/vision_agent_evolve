---
name: refocus_chart_chartqa_v_bar_extrema
description: "SOP for vertical-bar extrema questions on Refocus_Chart."
level: mid
depends_on: ["focus_on_x_values_with_draw", "refocus_chart_region_crop"]
applicability_conditions: "Use for vertical-bar questions asking about the highest, lowest, largest, smallest, or the difference between extrema."
---

## SOP
1. Confirm this applies: the chart is vertical and the question is about highest/lowest bars or a difference between extrema.
2. First inspect the full chart to identify the candidate extreme bars.
3. Once you identify one or two candidate x-axis labels, run `python -m tools focus_on_x_values_with_draw <image_path>`.
4. Then run `python -m tools refocus_chart_region_crop <image_path>` on those candidate labels with the `x_values_bbox` JSON mapping to verify the local evidence.
5. If the task asks for the difference between highest and lowest bars, compute that difference explicitly before answering.
6. Return only the final value or label name.
