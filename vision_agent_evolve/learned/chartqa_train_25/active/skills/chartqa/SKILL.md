---
name: chartqa
description: "SOP for accurately extracting and approximating numerical data from bar charts"
level: mid
depends_on: []
applicability_conditions: "Use this SOP for all task family questions requiring numerical approximations from bar charts, especially when a specific tool is available to enhance accuracy."
        ---

## SOP
1. Confirm this applies: Use the validated tool output to answer this task family.
2. Run `python -m tools chart_bar_approximation_tool <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
