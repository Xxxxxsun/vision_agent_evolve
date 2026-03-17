---
name: billiards_case_2_failure_lesson
description: "Failure lesson for trajectory prediction in billiards tasks involving directional indicators."
level: low
depends_on: []
applicability_conditions: "When the task involves predicting the path of a ball based on a visual direction indicator (e.g., an arrow) and calculating reflections off table boundaries."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example.
2. Helpful method: The original image shows a blue ball with a green arrow pointing down-left. The tool-generated artifacts incorrectly trace the path from the ball in the wrong direction (up-right or down-right) instead of following the green arrow's down-left orientation. The current tool is producing incorrect visual artifacts. A more reliable tool is required to correctly calculate the trajectory based on the arrow's actual direction.
3. Common mistake: The existing path tracer tool is failing to correctly identify the direction of the green arrow, leading to incorrect trajectory calculations.
4. Next time, consider: A more robust path-tracing tool that correctly identifies the vector from the green arrow and simulates reflections off the table rails.
