---
name: hrbench_single
description: "Identify the color of a backpack carried by a man wearing a yellow shirt using the designated tool."
level: mid
depends_on: []
applicability_conditions: "Use this SOP when identifying backpack color from images in hrbench_single tasks."
        ---

## SOP
1. Confirm this applies: Use the validated tool output to answer this task family.
2. Run `python -m tools color_recognition_tool <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, Targeting cluster_2 could improve precision in single-instance identification tasks. Generating a tool for better color recognition can raise overall accuracy more effectively than targeting cluster_1, given recent rejections. This cluster involves clear visual identification errors where a tool could realistically enhance outcomes.
