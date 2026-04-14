---
name: refocus_chart_chartqa_v_bar_extrema
description: "SOP for vertical-bar extrema questions: identify the highest/lowest bar, its label, its value, or compute the difference between extrema."
level: mid
depends_on: ["focus_on_x_values_with_draw"]
applicability_conditions: "Use for vertical-bar questions asking which bar is highest/lowest, what its value is, or what the difference between the two extremes is."
---

## SOP

1. Scan the full chart image to identify the approximate extreme bars (tallest and shortest visible bars).

2. Note the 1–2 candidate label names from the x-axis labels listed in context that correspond to these extreme bars.

3. If you need to confirm exact values, run the tool on those candidate labels:
   ```
   python -m tools focus_on_x_values_with_draw <image_path> '["<max_label>", "<min_label>"]' '<x_values_bbox JSON from context>'
   ```

4. If the extreme bar is visually obvious and you are confident in the value, skip the tool and answer directly.

5. Compute the answer:
   - "Which bar is highest/lowest?" → return the label name only.
   - "What is the value of the highest/lowest bar?" → return the number only.
   - "What is the difference between highest and lowest?" → subtract and return the number.

6. Format rules:
   - Return only the final value or label — no sentence, no extra units.
   - Yes/no: return exactly `Yes` or `No`.

7. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
