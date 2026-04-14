---
name: refocus_chart_chartqa_v_bar_count_or_total
description: "SOP for vertical-bar counting and aggregation questions: count how many bars meet a condition, sum named bar values, or answer yes/no about an aggregate."
level: mid
depends_on: ["focus_on_x_values_with_draw"]
applicability_conditions: "Use for vertical-bar questions that ask how many bars/categories exist, how many exceed a threshold, or for a sum/total of named bar values."
---

## SOP

1. Decide which sub-type applies:

   **A. Pure counting (how many bars/categories are shown, or how many exceed a threshold)**
   - Count directly from the x-axis labels listed in context — no tool needed.
   - For threshold counting, inspect the original chart visually and count.

   **B. Sum or aggregate of named categories**
   - Run the tool on the named categories to read their values precisely:
     ```
     python -m tools focus_on_x_values_with_draw <image_path> '["<label_1>", "<label_2>"]' '<x_values_bbox JSON from context>'
     ```
   - Read the values from the observation, sum or aggregate as required.

   **C. Yes/no about an aggregate**
   - Use sub-type B to get the values, then apply the boolean condition.

2. If the tool fails, read bar values directly from the original chart.

3. Format rules:
   - Count result: return an integer (e.g., `4`).
   - Sum result: return the number only.
   - Yes/no: return exactly `Yes` or `No`.
   - Do not add units, explanation, or a sentence.

4. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
