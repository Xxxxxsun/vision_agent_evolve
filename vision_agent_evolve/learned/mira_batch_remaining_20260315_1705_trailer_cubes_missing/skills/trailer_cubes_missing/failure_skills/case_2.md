---
name: trailer_cubes_missing_case_2_failure_lesson
description: "Guidance for reconstructing 3D volumes from orthographic projections to determine missing cube counts."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires calculating the number of missing cubes to complete a solid 3D structure based on multiple 2D views (top, side, front/back)."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image shows three orthographic projections (Side, Back, Top) of a 3D structure made of orange cubes on a trailer. The task requires spatial reasoning that is difficult for VLMs; providing a structured grid-mapping tool will reduce the cognitive load and improve accuracy.
3. Common mistake: The agent struggles to mentally reconstruct the 3D grid from 2D projections and count the missing cubes accurately.
4. Next time, consider: A systematic voxel-grid reconstruction tool that maps the projections to a 3D coordinate system.
