---
name: rolling_dice_sum_case_14_failure_lesson
description: "Failure lesson for tracking die orientation during grid-based rolling tasks."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires calculating the sum of bottom faces of a die as it moves along a path on a grid."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a die on a grid with a path. The artifacts highlight the grid and the die but do not explicitly trace the sequence of rolls or the bottom face values. The agent cannot mentally maintain the die's rotation state over multiple steps; a simulation tool is required to compute the bottom face at each step.
3. Common mistake: The agent struggles to track the 3D state of the die (orientation) through a sequence of 2D grid movements.
4. Next time, consider: A step-by-step simulation of the die's orientation (top, front, right faces) at each grid intersection along the path.
