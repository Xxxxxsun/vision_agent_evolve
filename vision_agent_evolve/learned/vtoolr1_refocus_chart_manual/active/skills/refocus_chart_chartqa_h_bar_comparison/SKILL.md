---
name: refocus_chart_chartqa_h_bar_comparison
description: "SOP for horizontal-bar comparison questions: compare two or more named bars, compute a difference, or answer a yes/no about their relative values."
level: mid
depends_on: ["focus_on_y_values_with_draw"]
applicability_conditions: "Use for horizontal-bar questions that compare two or more named categories, compute a difference, or ask a boolean about their relative magnitudes."
---

## SOP

1. Identify the two (or more) category labels named in the question. Match them against the available y-axis labels listed in context.

2. Run the focus tool with ALL relevant labels together so they appear side-by-side in the output:
   ```
   python -m tools focus_on_y_values_with_draw <image_path> '["<label_A>", "<label_B>"]' '<y_values_bbox JSON from context>'
   ```

3. From the observation image, read the bar values for each highlighted row carefully.

4. Compute the requested result:
   - **Difference**: subtract the smaller from the larger (or as the question specifies the direction).
   - **Sum**: add the values.
   - **Boolean (yes/no)**: apply the comparison and return exactly `Yes` or `No`.
   - **Ratio**: compute and express as the question format implies (e.g., a plain number like `2.13`).

5. If the tool fails or labels are not found in the bbox metadata, read the values directly from the original chart.

6. Format rules:
   - Numeric result: return only the number. Include `%` only if the chart explicitly labels the axis with percentages.
   - Yes/no: return exactly `Yes` or `No` with no extra text.
   - Do not add a sentence, explanation, or units beyond what the chart shows.

7. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
