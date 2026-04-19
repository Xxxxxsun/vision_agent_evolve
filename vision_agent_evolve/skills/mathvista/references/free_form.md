---
name: mathvista_free_form
description: "Branch detail for MathVista free-form (open-ended) questions"
level: low
---

# MathVista — Free-form Branch

## Trigger
- The question is open-ended: no labeled answer choices are provided.
- The final answer is a number, expression, or short text returned directly.

## Procedure
1. Identify the exact quantity or value the question requests.
2. Extract all required measurements, coordinates, or data points from the figure:
   - Use zoom_image to read small tick marks, angles, or annotated values.
   - Use crop_image for dense coordinate axes or crowded diagram regions.
3. Use execute_python for any non-trivial calculation:
   ```python
   # Always print the result
   angle_a = 35   # read from figure
   angle_b = 90   # given or read
   result = 180 - angle_a - angle_b
   print(result)
   ```
4. Determine the expected answer format:
   - Integer (e.g., 45) vs decimal (e.g., 3.14)
   - With or without units (e.g., "45°" vs "45")
   - Expression vs evaluated number
5. Return the final answer directly in Final answer — no option letter.

## Format Rules
- If the question involves angle: check whether degrees or radians are expected.
- If the question involves area or length: include the unit only if the question uses one.
- If the answer is a fraction: evaluate it as a decimal unless the question clearly wants a fraction.
- Round to the same decimal precision as values given in the figure, or to 2 decimal places if unclear.

## execute_python Templates

```python
# Geometry: angle sum
a, b = 55, 70
third_angle = 180 - a - b
print(third_angle)

# Coordinate: distance between two points
import math
x1, y1 = 1, 2
x2, y2 = 4, 6
dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
print(round(dist, 2))

# Statistics: mean
values = [12, 15, 9, 18, 11]
print(sum(values) / len(values))

# Percentage
part = 35
total = 140
print(round(part / total * 100, 1))
```

## Failure Checks
- Do not return an option letter — this is a free-form answer.
- Do not approximate a readable exact value — read it precisely.
- Do not skip execute_python for multi-step calculations — hand arithmetic is error-prone.
- If the figure shows a specific numeric annotation, use that exact number rather than estimating from scale.
