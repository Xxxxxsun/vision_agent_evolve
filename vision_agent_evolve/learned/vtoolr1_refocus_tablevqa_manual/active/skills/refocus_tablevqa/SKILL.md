---
name: refocus_tablevqa
description: "SOP for table VQA questions on Refocus_TableVQA: look up cell values, compare rows or columns, count entries, or answer yes/no about table data."
level: mid
depends_on: ["focus_on_columns_with_draw", "focus_on_rows_with_draw"]
applicability_conditions: "Use for all Refocus_TableVQA questions involving structured tables with column and row labels."
---

## SOP

1. Read the question carefully and identify the sub-type:

   **A. Lookup / single cell value** — question asks for the value of one specific cell (e.g., "What is the value of column X for row Y?")
   - Focus on the target column using the `columns_bbox` JSON from context:
     ```
     python -m tools focus_on_columns_with_draw <image_path> '["<target_column>"]' '<columns_bbox JSON from context>'
     ```
   - Then (if needed) use the row tool to isolate the target row:
     ```
     python -m tools focus_on_rows_with_draw <image_path> '["<target_row>"]' '<row_starters JSON from context>'
     ```
   - Read the cell value from the observation.

   **B. Comparison between two cells or rows** — question compares two named rows or columns
   - Focus on both relevant columns (or rows) at once:
     ```
     python -m tools focus_on_columns_with_draw <image_path> '["<col_A>", "<col_B>"]' '<columns_bbox JSON from context>'
     ```
   - Read the values, compute the comparison (difference, ratio, or boolean).

   **C. Counting** — question asks how many rows/columns satisfy a condition
   - Count from the row/column labels listed in context when possible (no tool needed).
   - For value-based counting, use the column or row tool to isolate the relevant column and count visually.

   **D. Aggregation (sum / average)** — question asks for a total or average over named rows/columns
   - Use the column tool to isolate the relevant column:
     ```
     python -m tools focus_on_columns_with_draw <image_path> '["<target_column>"]' '<columns_bbox JSON from context>'
     ```
   - Read all values in the column and compute the aggregate.

   **E. Yes/no / boolean** — question asks whether a condition holds
   - Gather the required values using the appropriate sub-type above, then apply the condition.
   - Return exactly `Yes` or `No`.

2. If both a column and row need to be isolated, run the column tool first, then the row tool on the resulting artifact path.

3. If the tool fails or the relevant label is not in the context bbox metadata, answer directly from the original table image.

4. Format rules:
   - Numeric value: return only the number. Do not add currency/units unless the table header includes them.
   - Yes/no: return exactly `Yes` or `No`.
   - Text answer (name, label): return only the text, no sentence.
   - Do NOT add explanation, context sentences, or trailing punctuation beyond what the expected answer format requires.

5. Output:
   ```
   Final Answer: <answer>
   ACTION: TASK_COMPLETE
   ```
