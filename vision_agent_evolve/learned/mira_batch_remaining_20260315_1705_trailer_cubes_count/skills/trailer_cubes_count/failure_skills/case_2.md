---
name: trailer_cubes_count_case_2_failure_lesson
description: "Guidance on integrating multi-view projections to determine 3D cube counts."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires calculating the maximum possible number of cubes based on multiple orthographic projections (top, side, back/front)."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows three views (Side, Back, Top) of a cube structure. The artifact overlays a grid on the top view but fails to provide a 3D reconstruction or a systematic way to map heights across views. The agent consistently fails to perform the 3D spatial reasoning required to integrate the views. A tool that forces the extraction of a height map will simplify the problem to a simple summation task.
3. Common mistake: The agent cannot mentally integrate the 2D views into a 3D volume count. The existing tool only highlights the top view without helping to correlate heights from the side/back views.
4. Next time, consider: A tool that explicitly maps the height of each grid cell in the top view using the side and back views as constraints.
