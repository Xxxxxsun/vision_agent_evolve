---
name: overlap_case_14_failure_lesson
description: "Lesson on improving spatial reasoning for shape intersection tasks."
level: low
depends_on: []
applicability_conditions: "When the task requires comparing the overlapping area of multiple shapes positioned within coordinate-bordered frames."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image contains four panels (A, B, C, D) with distinct shapes: an arrow, a star, a hexagon, and a heart, each positioned differently within their respective grid-bordered squares. Visual estimation of overlap is prone to error. A precise geometric overlay tool will allow the agent to see the intersection directly and compare the areas.
3. Common mistake: The agent failed to accurately estimate the spatial overlap of the shapes when mentally or visually superimposed, leading to an incorrect guess.
4. Next time, consider: A tool that performs pixel-wise logical AND operations on selected image pairs to visualize and quantify the overlapping area.
