---
name: refocus_tablevqa
description: "SOP for table VQA questions."
level: mid
depends_on: []
applicability_conditions: "Use for any table image question."
---

## SOP

### Step 1 — Locate the relevant cell(s)

Read the question and identify:
- Which row (by the value in the first/leftmost column, or by row index)
- Which column (by the column header)

Then find the cell at their intersection.

For counting questions ("how many rows have X?"), scan the relevant column from top to bottom and count matching entries.

### Step 2 — Read and answer

Read the exact value from the cell or count. Be careful with:
- Numbers that look similar (e.g., 1 vs 7, 0 vs 6)
- Multi-line cells (the full content may span multiple lines)
- The question may ask about a column header itself, not a cell value

### Step 3 — Output format (strict)

- Numeric value: digits only, e.g. `4` or `3.14`. No units.
- Yes/No: exactly `Yes` or `No`.
- Single text value: exact text from the cell, no extra words.
- Multiple values listed together: separate with `|` (pipe, no spaces), e.g. `A|B|C`.
- Do NOT add explanations, units, or full sentences.

Final answer: <answer>
