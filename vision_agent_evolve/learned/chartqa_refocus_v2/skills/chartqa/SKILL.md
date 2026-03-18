---
name: chartqa
description: "Extract labeled names from chart bars to identify relevant data points and people associated with visual data segments."
level: mid
depends_on: []
applicability_conditions: "Use this SOP when solving questions related to identifying people or extracting data from labeled chart bars in ChartQA tasks where charts feature labeled segments distinguished by visual cues such as color."
---

## SOP
1. Confirm this applies: Ability to read labeled names associated with chart bars
2. Run `python -m tools extract_chart_labels <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The image shows a horizontal bar chart with various TV hosts including Jon Stewart, with segments showing different favorability ratings in color-coded bars. The agent needs a tool to read and interpret labels to identify individuals connected to visual data in charts directly.
