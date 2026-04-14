---
name: refocus_chart_h_bar
description: "SOP for all horizontal-bar chart questions using VTool-R1 bbox focus tools."
level: mid
depends_on: ["focus_on_y_values_with_draw"]
applicability_conditions: "Use for any horizontal-bar chart question."
---

## SOP

### Step 1 — Find the target label

Look at the question and the "Available y-axis labels" list in your context.

- If the question names one or more specific bars (e.g., "What is the value for Haiti?", "How much larger is Albania than Cameroon?"), identify those label names. → Go to Step 2.
- If the question asks about a general property that does NOT require reading a specific bar's numeric value (e.g., "What color is the longest bar?", "What is the title?", "How many bars are shown?"), skip Step 2 and go directly to Step 3.

### Step 2 — Run the focus tool exactly once

Your context contains a "Tool call format" section showing an example command with the real bbox JSON already filled in, like this:

```
python -m tools focus_on_y_values_with_draw <image_path> '["Haiti"]' '{"Haiti":{...},"Libya":{...},...}'
```

Copy that command verbatim. Change **only** the label(s) inside the first JSON list (e.g., replace `"Haiti"` with your target label). Keep `<image_path>` and the entire third argument (the big bbox JSON) exactly as shown.

Run this command once. Then immediately proceed to Step 3 — do NOT retry even if the output seems empty.

### Step 3 — Read and answer

- If Step 2 produced an output image: read the answer from that image.
- Otherwise: read the answer directly from the original chart image.

### Step 4 — Format and output

Rules (strict):
- Numeric value: digits only, e.g. `5.32` or `203`. Add `%` only if the chart axis shows percentages.
- Yes/No: exactly `Yes` or `No`.
- Category name: exact label text only.
- Do NOT add units, sentences, or explanation.

Output exactly these two lines:
```
Final Answer: <answer>
ACTION: TASK_COMPLETE
```
