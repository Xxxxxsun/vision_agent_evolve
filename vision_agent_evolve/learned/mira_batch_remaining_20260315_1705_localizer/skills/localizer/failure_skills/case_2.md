---
name: localizer_case_2_failure_lesson
description: "Improving spatial mapping from local puzzle pieces to global grid coordinates."
level: low
depends_on: []
applicability_conditions: "Relevant when a task requires tiling a grid with puzzle pieces and identifying specific feature locations (like circles) within the final assembly."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Use the validated tool output to answer this task family.
3. Common mistake: The agent is failing to correctly map the relative coordinates of the circles within the puzzle pieces to their absolute positions on the 7x7 target grid.
4. Next time, consider: A geometric transformation or grid-alignment step is needed to map piece-local coordinates to the target grid.
