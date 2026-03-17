---
name: rolling_dice_two_case_2_failure_lesson
description: "Lesson on systematic die orientation tracking during grid-based path traversal."
level: low
depends_on: []
applicability_conditions: "When the task requires tracking the bottom face of a die across multiple sequential rotations on a grid."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Use the validated tool output to answer this task family.
3. Common mistake: The agent struggles to track the orientation of the die through multiple rotations along the grid paths, leading to incorrect bottom-face calculations.
4. Next time, consider: A systematic step-by-step state tracking tool that records the die's orientation (top, front, right) at each grid cell.
