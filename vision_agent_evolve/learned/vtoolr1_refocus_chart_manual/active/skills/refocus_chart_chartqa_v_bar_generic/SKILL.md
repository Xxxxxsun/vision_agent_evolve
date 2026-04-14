---
name: refocus_chart_chartqa_v_bar_generic
description: "SOP for generic vertical-bar chart questions: read a named bar's value or answer a general question about one category."
level: mid
depends_on: ["focus_on_x_values_with_draw"]
applicability_conditions: "Use for vertical-bar chart questions that name one specific category or ask about a single bar's value."
---

## SOP

1. Read the question. Identify whether it names a specific bar by its x-axis label.

2. If the question names a specific category label and that label appears in the available x-axis labels listed in context:
   - Run the focus tool with that label and the full `x_values_bbox` JSON provided in context:
     ```
     python -m tools focus_on_x_values_with_draw <image_path> '["<target_label>"]' '<x_values_bbox JSON from context>'
     ```
   - From the observation image, read the bar value at the highlighted column.

3. If the question does NOT name a specific label (asks about a color, title, or general chart property), answer directly from the original chart without using a tool.

4. If the tool fails or the observation is unclear, fall back to reading the value directly from the original chart image.

5. Format rules:
   - Numeric value: return only the number. Include `%` only if the chart's axis explicitly shows percentages.
   - Yes/no: return exactly `Yes` or `No`.
   - Category name: return only the name, no sentence.
   - Do NOT add explanation or extra text.

6. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
