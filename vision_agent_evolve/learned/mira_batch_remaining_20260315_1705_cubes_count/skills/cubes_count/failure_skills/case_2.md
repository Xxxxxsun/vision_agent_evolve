---
name: cubes_count_case_2_failure_lesson
description: "Addressing spatial reasoning failures in 3D block counting tasks."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires counting objects in a 3D structure where some cubes are obscured or serve as structural support for visible ones."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a 3D structure made of cubes. The tool-generated artifact successfully highlights the top faces of all visible cubes with green outlines. The tool already provides a perfect segmentation of the top faces. The failure is purely cognitive: the agent lacks the spatial reasoning skill to infer the total volume from the surface projection.
3. Common mistake: The agent is struggling to count the hidden cubes that support the visible ones, as it only perceives the surface layer.
4. Next time, consider: A systematic counting strategy that accounts for the depth/hidden layers of the 3D structure.
