---
name: cubes_missing_case_15_failure_lesson
description: "Failure lesson for spatial reasoning in 3D cube-filling tasks."
level: low
depends_on: []
applicability_conditions: "Relevant when the agent is asked to calculate the number of missing cubes to complete a solid 3D structure."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a 3D structure made of light blue cubes. The grid overlay tool successfully highlights the individual cube faces, but the agent still miscounts the total missing cubes. The visual information is already clear with the grid overlay; the failure is in the counting strategy/logic, not the lack of visual data.
3. Common mistake: The agent struggles with spatial reasoning and occlusion, failing to account for hidden gaps or the full 3D volume required to complete the block.
4. Next time, consider: A systematic way to decompose the 3D structure into layers or columns to count existing vs. total required cubes.
