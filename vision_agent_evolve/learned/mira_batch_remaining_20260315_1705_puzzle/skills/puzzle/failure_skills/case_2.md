---
name: puzzle_case_2_failure_lesson
description: "Lesson on improving geometric and pattern matching for jigsaw-style puzzle tasks."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires identifying a specific puzzle piece to fill a cutout in an image based on shape, texture, or color continuity."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a fish with a jagged white cutout on its side and five potential puzzle pieces (A-E) below it. The task requires fine-grained visual matching which the agent is failing at; isolating the regions of interest will force the model to focus on the specific geometric features.
3. Common mistake: The agent failed to perform a precise geometric and color-pattern matching between the jagged cutout and the candidate pieces.
4. Next time, consider: A tool to crop and isolate the cutout area and the candidate pieces for side-by-side comparison.
