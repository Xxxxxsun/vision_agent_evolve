---
name: mathvista
description: "MathVista solver — read image directly, use execute_python for arithmetic verification"
level: mid
tool_names: ["execute_python"]
applicability_conditions: "Use for all MathVista questions involving geometry, charts, statistics, or arithmetic that must be verified."
---

# MathVista — Direct Read + Python Verify

## Core Principle

Read visual values **directly from the original image** — do not call zoom or crop.
Use `execute_python` only when arithmetic verification is needed after you have extracted the values.

## Step-by-Step Procedure

1. **Inspect the image carefully**. Read all labeled values, angles, lengths, tick marks, or bar heights directly at the original scale.
2. **Write down the extracted values** in your reasoning trace.
3. **Compute** with `execute_python` when any non-trivial arithmetic is involved — always `print()` the result.
4. **Return the answer** in the required format.

## When to Call execute_python

- Arithmetic: addition, subtraction, multiplication, division
- Geometry: area, perimeter, Pythagorean theorem, angle sum, trigonometry
- Statistics: mean, median, percentage, ratio, standard deviation
- Evaluating which numeric MCQ option matches your computed result

```python
# Always print() — silent assignments produce no output

# Geometry: angle sum
a, b = 55, 70
print(180 - a - b)

# Statistics: mean
values = [12, 15, 9, 18, 11]
print(round(sum(values) / len(values), 2))

# Percentage
print(round(35 / 140 * 100, 1))

# Check MCQ options
for label, val in [("A", 6), ("B", 8), ("C", 10), ("D", 12)]:
    print(label, val**2 + 2*val)
```

## When NOT to Call execute_python

- Pure visual pattern / sequence ("comes next", matrix completion) → answer directly
- Yes/No MCQ → answer directly
- Simple object count visible at a glance → answer directly
- When the answer can be read directly from a labeled axis or annotation

## Answer Format Rules

- **MCQ**: option letter only. Example: `Final answer: C`
- **Free-form integer**: one whole number, no units. Example: `Final answer: 45`
- **Free-form float**: one decimal at the precision the question implies. Example: `Final answer: 3.14`
- Never include units, formulas, fractions, alternatives, or explanations in the final answer line.
