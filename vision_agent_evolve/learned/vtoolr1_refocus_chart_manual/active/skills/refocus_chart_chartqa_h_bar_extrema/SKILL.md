---
name: refocus_chart_chartqa_h_bar_extrema
description: "SOP for horizontal-bar extrema questions: identify the highest/lowest bar, its label, its value, or compute the difference between extrema."
level: mid
depends_on: ["focus_on_y_values_with_draw"]
applicability_conditions: "Use for horizontal-bar questions asking which bar is highest/lowest/largest/smallest, what its value is, or what the difference between the two extremes is."
---

## SOP

1. Scan the full chart image to identify the approximate extreme bars (the longest and shortest visible bars).

2. Note the 1–2 candidate label names from the y-axis labels listed in context that correspond to these extreme bars.

3. If you need to confirm exact values (e.g., two bars look similar, or the question asks for a precise numeric difference), run the tool on those candidate labels:
   ```
   python -m tools focus_on_y_values_with_draw <image_path> '["<candidate_label>"]' '<y_values_bbox JSON from context>'
   ```
   Repeat for the second extreme label if needed, OR pass both at once:
   ```
   python -m tools focus_on_y_values_with_draw <image_path> '["<max_label>", "<min_label>"]' '<y_values_bbox JSON from context>'
   ```

4. If the extreme bar is visually obvious and you are confident in the label and value, you may skip the tool call and answer directly.

5. Compute the answer:
   - "Which bar is highest/lowest?" → return the label name only.
   - "What is the value of the highest/lowest bar?" → return the number only.
   - "What is the difference between highest and lowest?" → subtract and return the number.

6. Format rules:
   - Return only the final value or label — no sentence, no units beyond what the chart shows.
   - Yes/no: return exactly `Yes` or `No`.

7. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
