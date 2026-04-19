---
name: mathvista
description: "Visual reading and reasoning SOP for math figures — no tools"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: []
applicability_conditions: "Use for MathVista questions requiring visual extraction of numeric values, geometric properties, or data from a figure."
---

# MathVista — Visual Reading and Reasoning

## Trigger
- The question requires reading labeled values, geometric properties, or data from a mathematical figure.
- Figure types: geometry diagram, coordinate/function graph, data bar/line chart, statistical plot, logical diagram.

## Routing
- If the question has labeled answer choices → follow the MCQ procedure (return option letter).
- If the question is open-ended → follow the Free-form procedure (return number or text directly).

## Common Procedure
1. Identify what visual quantities the question requires: specific numbers, angles, lengths, coordinates, labels, or trend direction.
2. Locate those quantities in the figure:
   - **Geometry**: look for numeric labels near vertices, along edges, or inside angles.
   - **Coordinate/function graph**: read y-axis tick values at the relevant x-position; trace from the data point horizontally to the y-axis scale.
   - **Bar/line data chart**: same approach as ChartQA — confirm the series, read from the axis scale.
   - **Table**: find the row and column that intersect at the needed value.
3. Write down all extracted values in your reasoning trace.
4. Compute if needed: show each calculation step explicitly. Do not skip steps.

## MCQ Procedure
- Read all answer choices first to understand the expected type and range of the answer.
- Extract values and compute. Compare the result to the choices and select the closest one.
- If choices are expressions, evaluate each and pick the matching one.
- Return only the option letter.

## Free-form Procedure
- Extract all needed values and compute step by step.
- Confirm the unit (degrees, cm, %, etc.) from the figure before finalizing.
- Return the number or short text directly (no option letter).
- Match the decimal precision of values given in the figure; round to 1–2 decimal places if unclear.

## Failure Checks
- Do not estimate a value that is explicitly labeled in the figure — read the exact number.
- Do not mix up units (e.g., degrees vs radians, cm vs m).
- For MCQ: always map your result to an option letter; never return the raw number.
- For geometry angle problems: remember angle sum rules (triangle = 180°, straight line = 180°).
