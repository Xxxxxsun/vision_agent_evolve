---
name: mathvista
description: "Router skill for visual math questions requiring figure inspection and optional calculation"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
applicability_conditions: "Use for MathVista questions that require reading numeric values, geometric properties, or data from a figure and optionally computing a result."
---

# MathVista

## Trigger
- The question requires extracting a numeric value, geometric property, or data point from a mathematical figure (geometry diagram, function graph, data plot, table, or logic puzzle).
- The answer may be a multiple-choice option letter or a direct numeric/textual answer.

## Routing Rule
1. If the question provides labeled answer choices (A, B, C, D …), follow the **MCQ branch** — return an option letter.
2. If the question is open-ended (no labeled choices), follow the **Free-form branch** — return a number or short text directly.

See branch detail:
- `references/mcq.md`
- `references/free_form.md`

## Common Procedure (both branches)
1. Identify what visual quantities the question requires: specific numbers, angles, lengths, coordinates, or labels in the figure.
2. If those quantities are small, annotated, or hard to read at the original scale, use `zoom_image`:
   - Estimate where the target value is in the image (center_x, center_y in [0, 1]).
   - Use factor=2–3 for moderate details; factor=4 for very small annotations or tick marks.
3. If the relevant region is densely packed (e.g., a crowded coordinate axis), use `crop_image` after getting the image dimensions via `get_image_info`.
4. Once the values are clearly read, use `execute_python` for any arithmetic.
5. Format the final answer according to the branch (option letter or direct answer).

## Tool Hints

### zoom_image positioning by figure type:
- **Geometry diagram**: numbers/angles are usually near vertices or edges — estimate their position from the diagram structure.
- **Function graph / coordinate plot**: x-axis labels at center_y≈0.90, y-axis labels at center_x≈0.08, plot area at center=0.50.
- **Bar/line data plot**: same as ChartQA region rules (legends top-right, axis labels at edges).
- **Table**: rows and columns are spread across the image — zoom the specific cell needed.

### execute_python:
- Always extract the raw numbers first, then pass them to python.
- For geometry: compute angles, areas, or lengths from extracted measurements.
- For statistics: compute mean, median, or percentages.
- Always `print()` the result.

## Failure Checks
- Do not mix visual estimation with exact arithmetic — if a number is readable, use the exact value.
- Do not zoom to (0.5, 0.5) when the needed label is on an axis edge or corner.
- Re-check units (degrees, cm, %, etc.) before the final answer.
- For MCQ: always map the computed result to the closest option letter, do not return the raw number.
- For free-form: match the expected answer format (integer vs decimal, with or without units).
