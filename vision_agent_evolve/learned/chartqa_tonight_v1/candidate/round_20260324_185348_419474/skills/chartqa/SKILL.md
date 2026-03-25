---
name: chartqa
description: "Read chart values carefully and return the exact figure shown, preserving the chart’s numeric formatting."
level: mid
depends_on: []
applicability_conditions: "Applies to ChartQA questions that ask for a value directly read from a chart. Use this SOP when no extra tool is available and the chart itself provides the answer; no added step is needed beyond careful extraction."
        ---

## SOP
1. Identify the chart element (bar, line point, pie slice, label, or table entry) that matches the question’s category, group, and time/value reference.
2. Read the value exactly as displayed on the chart, including decimals, and verify the correct series/legend and axis alignment before answering.
3. Do not round, approximate, re-scale, or rewrite the number in expanded words unless the question explicitly asks for a different format; preserve the chart’s numeric precision.
4. Answer the original question using only the exact extracted value, adding units only if they are explicitly part of the chart label or question.
