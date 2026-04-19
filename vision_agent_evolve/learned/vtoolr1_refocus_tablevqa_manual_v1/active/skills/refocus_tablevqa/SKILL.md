---
name: refocus_tablevqa
description: "SOP for table VQA questions using function-calling focus tools."
level: mid
depends_on: []
applicability_conditions: "Use for any table image question."
---

## SOP

### Step 1 — Identify what needs to be located

Look at the question:
- If the question asks about a specific **row** (e.g., "What is the value for United States?", "How many points did Brazil score?") → identify the row label(s) and go to Step 2a.
- If the question asks about a specific **column** (e.g., "What are the values in the GDP column?", "Which country has the highest Population?") → identify the column label(s) and go to Step 2b.
- If the question asks about a **cell at the intersection** of a row and column → do both Step 2a and 2b.
- If the question does NOT require locating a specific cell (e.g., "How many rows are there?", "What is the table title?") → skip to Step 3.

### Step 2a — Highlight the target row (if needed, exactly once)

Call `focus_on_rows` with the target row label(s), e.g.:
```
focus_on_rows(labels=["United States"])
```
or for multiple rows:
```
focus_on_rows(labels=["Brazil", "Argentina"])
```

### Step 2b — Highlight the target column (if needed, exactly once)

Call `focus_on_columns` with the target column label(s), e.g.:
```
focus_on_columns(labels=["GDP"])
```

Do NOT retry even if uncertain — call each tool at most once, then proceed.

### Step 3 — Read and answer

- If Step 2 produced a derived image: read the answer from that highlighted image.
- Otherwise: read the answer directly from the original table image.

### Step 4 — Output format (strict)

- Numeric value: digits only, e.g. `42` or `3.14`. No units unless the table header shows them.
- Yes/No: exactly `Yes` or `No`.
- Text value: exact cell text only.
- Do NOT add units, sentences, or explanation.

Final answer: <answer>
