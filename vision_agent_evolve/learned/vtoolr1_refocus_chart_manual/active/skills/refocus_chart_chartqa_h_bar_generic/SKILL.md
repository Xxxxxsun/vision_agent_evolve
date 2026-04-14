---
name: refocus_chart_chartqa_h_bar_generic
description: "SOP for generic horizontal-bar Refocus_Chart questions using paper-aligned focus tools plus a tighter crop helper."
level: mid
depends_on: ["focus_on_y_values_with_draw", "refocus_chart_region_crop"]
applicability_conditions: "Use for generic horizontal-bar chart questions where one target category is named explicitly."
---

## SOP
1. Confirm this applies: the chart is horizontal and the question names one category or asks for the value of one visible bar.
2. If the target category is explicitly named in the question and appears in the available y-axis labels, first run `python -m tools focus_on_y_values_with_draw <image_path>`.
3. Then run `python -m tools refocus_chart_region_crop <image_path>` with a JSON list containing the same target label and the full `y_values_bbox` JSON mapping.
4. Use the artifact, not a vague impression from the raw image, to read the local bar value or nearby annotation.
5. If the question does not name a specific category, answer from the original chart without forcing the crop tool.
6. Return the shortest exact final answer string: just the value, yes/no, or category name.
