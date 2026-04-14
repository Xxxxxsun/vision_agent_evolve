---
name: refocus_chart_h_bar
description: "SOP for all horizontal-bar chart questions using function-calling focus tools."
level: mid
depends_on: []
applicability_conditions: "Use for any horizontal-bar chart question."
---

## SOP

### Step 1 — Identify whether a specific bar label is needed

Look at the question:
- If the question names one or more specific bars (e.g., "What is the value for Haiti?", "How much larger is Albania than Cameroon?") → identify those label(s) and go to Step 2.
- If the question does NOT require reading a specific bar's value (e.g., "What color is the longest bar?", "What is the title?", "How many bars are shown?") → skip to Step 3.

### Step 2 — Call the focus tool (exactly once)

Call `focus_on_y_values` with the target label(s) as a list, e.g.:
```
focus_on_y_values(labels=["Haiti"])
```
or for a comparison:
```
focus_on_y_values(labels=["Albania", "Cameroon"])
```

The tool returns a derived image with the target rows highlighted. Proceed to Step 3 immediately — do NOT retry even if uncertain.

### Step 3 — Read and answer

- If Step 2 produced a derived image: read the answer from that highlighted image.
- Otherwise: read the answer directly from the original chart image.

### Step 4 — Output format (strict)

- Numeric value: digits only, e.g. `5.32` or `203`. Add `%` only if the axis shows percentages.
- Yes/No: exactly `Yes` or `No`.
- Category name: exact label text only.
- Do NOT add units, sentences, or explanation.

Final answer: <answer>
