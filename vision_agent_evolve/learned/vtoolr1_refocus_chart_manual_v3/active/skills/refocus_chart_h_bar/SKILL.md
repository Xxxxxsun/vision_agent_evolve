---
name: refocus_chart_h_bar
description: "SOP for all horizontal-bar chart questions: read bar values, compare bars, count/aggregate, or answer general chart questions."
level: mid
depends_on: ["focus_on_y_values_with_draw"]
applicability_conditions: "Use for any horizontal-bar chart question (generic, comparison, extrema, count/total)."
---

## SOP

### Step 1 — Classify the question

- **Numeric read**: question asks for the value of one named bar (e.g. "What is the value for Haiti?")
- **Comparison**: question asks which of two/more named bars is larger/smaller, or the difference between them
- **Extrema**: question asks which bar has the highest/lowest value
- **Count/aggregate**: question asks how many bars exceed a threshold, or the sum of named bars
- **General**: question about a color, title, axis label, or anything not tied to a specific numeric value

### Step 2 — Tool use decision

**Use the focus tool only for Numeric read or Comparison** (when you need to read a precise value for a named category).

- Look at the "Task-specific instructions" in your context. It shows an example command with the real bbox JSON already filled in.
- Copy that example command, replace only the label name in the JSON list with your target label(s), and run it.
- Run the tool **at most once**. After the tool runs (whether it succeeds or fails), proceed immediately to Step 3 — do NOT retry.

**Skip the tool** for Extrema, Count/aggregate, and General questions — answer directly from the original chart image.

### Step 3 — Read the answer

- If the tool produced an output image: read the bar value from that image.
- If the tool produced no output or failed: read from the original chart image.
- For comparison questions requiring two values: if only one crop was produced, read the second value from the original.

### Step 4 — Format and complete

Format rules (strict):
- Numeric value: digits only, e.g. `5.32` or `203`. Include `%` only if the chart axis explicitly shows percentages.
- Yes/No answer: exactly `Yes` or `No`, nothing else.
- Category name: the exact label text, no sentence.
- Do NOT add units, explanation, or extra words.

Output exactly:
```
Final Answer: <answer>
ACTION: TASK_COMPLETE
```
