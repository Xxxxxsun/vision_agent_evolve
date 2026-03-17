---
name: billiards_case_11_failure_lesson
description: "Failure lesson for trajectory prediction in billiards tasks involving rail reflections."
level: low
depends_on: []
applicability_conditions: "When the task requires predicting the final pocket of a ball based on an initial trajectory vector and multiple potential rail reflections."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example.
2. Helpful method: The original image shows a blue ball and a green arrow on a billiards table. The tool-generated artifact shows a red line extending from the ball in the direction of the arrow, but it stops abruptly without simulating the full trajectory or reflections. The current tool is insufficient because it does not solve the physics of the problem (reflections). A tool that computes the full path is required to determine the final pocket.
3. Common mistake: The current tool only visualizes the initial vector rather than calculating and drawing the full path of the ball including reflections off the rails.
4. Next time, consider: A full trajectory simulation tool that calculates reflections until the ball hits a pocket.
