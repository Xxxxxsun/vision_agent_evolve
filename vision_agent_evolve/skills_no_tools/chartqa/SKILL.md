---
name: chartqa
description: "Visual inspection SOP for chart reading — no tools"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: []
final_answer_policy: direct_answer
applicability_conditions: "Use for ChartQA questions about values, comparisons, maxima/minima, and short chart text."
---

# ChartQA — Visual Inspection

## Trigger
- The question asks for a numeric value, a comparison, a maximum/minimum, or a short text label from a chart.
- Answer is direct (number or short text), not an option letter.

## Procedure
1. Identify the chart type: bar chart, line chart, pie chart, or other.
2. Find the specific series or category the question asks about:
   - Read the chart legend (typically in a corner) and match colors or patterns to series names.
   - Locate the specific bar, line segment, or pie slice.
3. Read the value:
   - For bar/line charts: trace horizontally from the top of the bar or the data point to the y-axis scale and read the tick value.
   - For pie charts: read the percentage or label directly on or near the slice.
4. For comparison questions: read both values individually, then compute the difference or ratio mentally.
5. For maximum/minimum questions: scan all visible bars or data points and identify the tallest/shortest/highest/lowest.
6. Return the final value as a number or short text directly.

## Reading Tips
- Always confirm which series you are reading by checking the legend color/pattern.
- The y-axis scale is on the left edge — trace a horizontal grid line from the bar top to that scale.
- X-axis category labels are at the bottom — confirm the label matches the question before reading the value.
- Unit notation (%, K, M) is usually at the top of the y-axis or in the axis title — apply it to your reading.
- For stacked bars: read individual segments by identifying the segment boundaries.

## Failure Checks
- Do not read the wrong bar — confirm the x-axis label matches the category in the question.
- Do not confuse adjacent series — verify the legend color matches the element you are reading.
- Do not return an option letter — ChartQA answers are numeric or short text.
- If two adjacent values look equal, choose the one whose bar/line visually aligns better with the grid line.
