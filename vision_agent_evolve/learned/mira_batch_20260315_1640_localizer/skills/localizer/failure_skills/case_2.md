---
name: localizer_case_2_failure_lesson
description: "Lesson on spatial reasoning and coordinate mapping for grid-based tiling tasks."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires placing geometric shapes into a constrained grid and identifying specific internal points (like circles) within those shapes."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows four puzzle pieces and a 7x7 grid. The tool-generated images correctly identify the center of the circles on the pieces but fail to perform the spatial reasoning required to place them into the 7x7 grid. The visual identification is complete; the failure is purely computational/spatial. A dedicated solver tool is required to handle the geometric constraints of the tiling.
3. Common mistake: The agent lacks the spatial reasoning capability to map the geometry of the pieces (triangles and irregular shapes) onto the grid coordinates.
4. Next time, consider: A geometric tiling solver that can compute the transformation (rotation/translation) of each piece into the grid.
