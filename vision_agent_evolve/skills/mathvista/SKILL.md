---
name: mathvista
description: "MathVista visual math solver — use zoom/crop to read the figure, execute_python to verify arithmetic"
level: mid
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
applicability_conditions: "Use for all MathVista questions involving geometry, charts, graphs, measurements, statistics, or any arithmetic that must be verified."
---

# MathVista — Visual Math Solver

## Core Principle: Tools First

For most MathVista questions, visual tools and Python are available and should be used proactively:
- **zoom_image / crop_image** — read numbers that are small, annotated, or ambiguous at the original scale
- **execute_python** — verify all non-trivial arithmetic; never trust mental calculation for multi-step problems

## Step-by-Step Procedure

1. **Read the question** carefully. Identify exactly what quantity is being asked for.
2. **Inspect the image**. If any required values are small, near the axes, or hard to read → call `zoom_image`.
   - Estimate `center_x` / `center_y` from where the target appears (0.0 = left/top, 1.0 = right/bottom).
   - Use `factor=2` for moderately small text; `factor=3–4` for tick marks, ruler graduations, angle labels.
   - Call `get_image_info` first if you need pixel dimensions for `crop_image`.
3. **Extract all needed values** from the (zoomed) image and write them in your reasoning trace.
4. **Compute** with `execute_python` whenever any arithmetic is involved — always `print()` the result.
5. **Return the answer** in the required format (see below).

## When to Use zoom_image
- Geometry: side-length annotations, angle labels, coordinate axis tick values
- Charts / bar graphs / line graphs: bar heights, y-axis scale values, legend text, x-axis labels
- Scientific diagrams: dial readings, ruler marks, measurement scales, arrow labels
- Any number or label that is printed small or near the edge of the image

## When to Use execute_python
- Any arithmetic: addition, subtraction, multiplication, division, exponentiation
- Geometry formulas: area, perimeter, Pythagorean theorem, angle sum rules, trigonometry
- Statistics: mean, median, percentage, ratio, standard deviation
- Evaluating numeric MCQ options to find which matches the computed result
- Coordinate geometry: distance, midpoint, slope, equation checks

```python
# Always print() — silent assignments produce no output
import math

# Example: geometry
a, b = 55, 70          # angles read from figure
third = 180 - a - b
print(third)

# Example: statistics
values = [12, 15, 9, 18, 11]
print(round(sum(values) / len(values), 2))

# Example: evaluate MCQ options
for label, val in [("A", 6), ("B", 8), ("C", 10), ("D", 12)]:
    print(label, val, val**2 + 2*val)
```

## When NOT to Use Tools
- Pure visual pattern / sequence completion ("which comes next", "complete the matrix") → answer directly
- Yes/No visual MCQ → answer directly
- Simple object counting visible at a glance → answer directly

## Answer Format Rules
- **MCQ**: return the option letter only. Example: `Final answer: C`
- **Free-form integer**: one whole number, no units or words. Example: `Final answer: 45`
- **Free-form float**: one decimal number at the precision the question implies. Example: `Final answer: 3.14`
- Never include units, formulas, fractions, alternatives, or explanations in the final answer line.
- If the answer is a fraction, convert to decimal unless the question clearly wants a fraction.
