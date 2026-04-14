---
name: refocus_chart_chartqa_v_bar_comparison
description: "SOP for vertical-bar comparison questions: compare two or more named bars, compute a difference, or answer a yes/no about their relative values."
level: mid
depends_on: ["focus_on_x_values_with_draw"]
applicability_conditions: "Use for vertical-bar questions that compare two or more named categories, compute a difference, or ask a boolean about their relative magnitudes."
---

## SOP

1. Identify the two (or more) category labels named in the question. Match them against the available x-axis labels listed in context.

2. Run the focus tool with ALL relevant labels together:
   ```
   python -m tools focus_on_x_values_with_draw <image_path> '["<label_A>", "<label_B>"]' '<x_values_bbox JSON from context>'
   ```

3. From the observation image, read the bar heights for each highlighted column carefully.

4. Compute the requested result:
   - **Difference**: subtract the smaller from the larger (or as the question directs).
   - **Sum**: add the values.
   - **Boolean (yes/no)**: apply the comparison and return exactly `Yes` or `No`.
   - **Ratio**: compute and return as a plain number.

5. If the tool fails or labels are not in the bbox metadata, read values directly from the original chart.

6. Format rules:
   - Numeric result: return only the number. Include `%` only if the chart axis shows percentages.
   - Yes/no: return exactly `Yes` or `No`.
   - Do not add a sentence, explanation, or extra units.

7. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
