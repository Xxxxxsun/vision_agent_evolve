---
name: refocus_tablevqa
description: "SOP for table VQA questions: crop to the relevant column before answering."
level: mid
depends_on: []
applicability_conditions: "Use for any table image question."
---

## SOP

### Step 1 — Identify the most relevant column

Read the question. Decide which column name contains the values you need to count, look up, or compare.

### Step 2 — Crop that column (always, before answering)

Look up the pixel coordinates for that column in the "Table region coordinates" section of this message.
Then call:

```
crop_image(image_id="image_0", left=<left>, top=<top>, right=<right>, bottom=<bottom>)
```

Use the exact coordinates from the table. This creates a narrow vertical strip showing only that column — much easier to count or scan than the full-width table.

- Call crop_image **exactly once**.
- If you cannot identify a single column (e.g. the question is purely structural like "how many columns are there?"), skip this step.

### Step 3 — Read and answer

Read the answer from the cropped column image. Count rows, find the cell value, or compare as needed.

### Step 4 — Output format (strict)

- Numeric value: digits only, e.g. `4` or `3.14`.
- Yes/No: exactly `Yes` or `No`.
- Text value: exact cell text only, no extra punctuation.
- Do NOT add units, sentences, or explanation.

Final answer: <answer>
