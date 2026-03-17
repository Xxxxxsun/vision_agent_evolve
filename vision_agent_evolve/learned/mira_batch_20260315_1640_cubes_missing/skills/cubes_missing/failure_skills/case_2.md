---
name: cubes_missing_case_2_failure_lesson
description: "Lesson on systematic 3D spatial decomposition to count missing cubes in a structure."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires calculating the number of missing cubes to complete a solid 3D block structure."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a 3D isometric structure of cubes. The tool-generated artifact overlays a grid, but the agent still miscounts the missing cubes. The grid tool is sufficient for visualization; the failure is in the counting logic. A structured counting algorithm (skill) will resolve the discrepancy.
3. Common mistake: The agent struggles to perform 3D spatial reasoning (counting missing cubes) even with the grid overlay, likely due to difficulty in identifying hidden gaps or correctly parsing the 3D volume.
4. Next time, consider: A systematic layer-by-layer or column-by-column counting strategy is needed to ensure no gaps are missed.
