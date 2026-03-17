---
name: billiards_case_2_failure_lesson
description: "Failure lesson for trajectory calculation in billiards-style reflection tasks."
level: low
depends_on: []
applicability_conditions: "When the task requires predicting the final destination of a ball based on a visual trajectory vector and table boundaries."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example.
2. Helpful method: The original image shows a billiards table with a blue ball and a green directional arrow. The tool-generated artifacts show an incorrect trajectory line that does not align with the ball's position or the arrow's vector. The current tool is producing visually incorrect paths, misleading the solver. A dedicated, accurate geometric calculator is required to solve the reflection problem.
3. Common mistake: The existing trajectory tool is failing to correctly calculate the reflection path based on the ball's actual position and the arrow's vector, resulting in an incorrect visual overlay.
4. Next time, consider: A more precise geometric calculation tool that correctly maps the vector from the ball's center and performs standard reflection math on the table boundaries.
