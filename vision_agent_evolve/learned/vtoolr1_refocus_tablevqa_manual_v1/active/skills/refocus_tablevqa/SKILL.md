---
name: refocus_tablevqa
description: "SOP for table VQA questions using function-calling focus tools."
level: mid
depends_on: []
applicability_conditions: "Use for any table image question."
---

## SOP

### Step 1 — Identify the relevant column(s) and/or row(s)

Read the question and identify:
- Which **column** contains the values you need to read or count (e.g., "GDP column", "Score column", "Year column")
- Which **row** you need to look at, if the question names a specific entity (e.g., "United States", "1995")

### Step 2 — Call the focus tool (call once, immediately, before answering)

**Always call a focus tool** unless the table is tiny (3 rows or fewer). Tables in this benchmark are often tall and hard to read without zooming.

- If a specific column is relevant:
  ```
  focus_on_columns(labels=["ColumnName"])
  ```
- If a specific row is relevant AND you know the row key:
  ```
  focus_on_rows(labels=["RowKey"])
  ```
- If both row and column matter, call `focus_on_columns` first (it gives a narrower view of the full column, making counting and scanning easier).

Examples:
```
focus_on_columns(labels=["Supporting Actor"])
focus_on_columns(labels=["GDP", "Population"])
focus_on_rows(labels=["1995"])
```

Call the tool exactly once, then proceed immediately to Step 3. Do NOT retry.

### Step 3 — Read and answer

- If Step 2 produced a derived image: read the answer from that highlighted image.
- Otherwise: read the answer directly from the original table image.

### Step 4 — Output format (strict)

- Numeric value: digits only, e.g. `42` or `3.14`.
- Yes/No: exactly `Yes` or `No`.
- Text value: exact cell text only.
- Do NOT add units, sentences, or explanation.

Final answer: <answer>
