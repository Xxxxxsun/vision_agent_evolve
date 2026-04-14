---
name: refocus_chart_chartqa_h_bar_generic
description: "SOP for generic horizontal-bar chart questions: read a named bar's value or answer a general question about one category."
level: mid
depends_on: ["focus_on_y_values_with_draw"]
applicability_conditions: "Use for horizontal-bar chart questions that name one specific category or ask about a single bar's value."
---

## SOP

1. Read the question. Identify whether it names a specific bar by its y-axis label.

2. If the question names a specific category label and that label appears in the available y-axis labels listed in context:
   - Run the focus tool with that label and the full `y_values_bbox` JSON provided in context:
     ```
     python -m tools focus_on_y_values_with_draw <image_path> '["<target_label>"]' '<y_values_bbox JSON from context>'
     ```
   - From the observation image, read the bar value at the highlighted row.

3. If the question does NOT name a specific label (asks about a general chart property, a color, a title, etc.), answer directly from the original chart without using a tool.

4. If the tool fails or the observation is unclear, fall back to reading the value directly from the original chart image.

5. Format rules for the final answer:
   - For a numeric value: return only the number (e.g., `5.32` or `203`). Include a `%` sign only if the chart's axis explicitly shows percentages.
   - For yes/no: return exactly `Yes` or `No`.
   - For a category name: return only the name, no sentence.
   - Do NOT add explanation, units beyond what the chart shows, or extra text.

6. Output the final answer in this exact format:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
