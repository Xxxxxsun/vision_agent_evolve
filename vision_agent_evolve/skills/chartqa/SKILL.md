---
name: chartqa
description: "ChartQA solver — read exact chart values, use execute_python for arithmetic"
level: mid
tool_names: ["execute_python"]
final_answer_policy: direct_answer
applicability_conditions: "Use for ChartQA questions about numeric values, comparisons, or short text labels from charts."
---

# ChartQA — Exact Read + Python Arithmetic

## Core Principle

Read chart values **directly from the original image** at the original scale.
Use `execute_python` only when arithmetic is needed after reading the values.

## Reading Values

1. Identify the target category or series — match it to the x-axis label or legend entry.
2. Read the value **exactly as shown**:
   - If a number is printed on or near the bar/point, use that exact number.
   - If estimating from the y-axis scale: align the bar top to the nearest tick and interpolate precisely.
3. Always verify the category label matches the question before reading — avoid reading the wrong bar or line.
4. Check the y-axis unit (%, K, M, billions) before extracting — apply it mentally.

## When to Call execute_python

- Difference or ratio between two values
- Percentage change or share
- Sum or mean across multiple values

```python
# Always print() — silent assignments produce no output

# Difference
a, b = 45.2, 32.1
print(round(a - b, 2))

# Percentage change
old, new = 120, 150
print(round((new - old) / old * 100, 1))

# Mean
values = [12.5, 18.3, 9.7]
print(round(sum(values) / len(values), 2))
```

## When NOT to Call execute_python

- Direct lookups (reading a single labeled value) — return it immediately
- Yes/No or text comparison — answer directly

## Answer Format

Return **only** the number or short text in Final answer — no units, no extra words, no explanation.
- Correct: `Final answer: 12.13`
- Wrong: `Final answer: 12.13 million children`
- Correct: `Final answer: Yes`
- Wrong: `Final answer: Yes, the blue bar is taller`
