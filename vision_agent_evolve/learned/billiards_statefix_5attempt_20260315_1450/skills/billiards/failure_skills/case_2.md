---
name: billiards_case_2_failure_lesson
description: "Failure lesson for trajectory projection and reflection on billiards tables."
level: low
depends_on: []
applicability_conditions: "When the task involves predicting the final pocket of a ball based on a visual direction indicator (arrow) and geometric reflection rules."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Use the validated tool output to answer this task family.
3. Common mistake: The trajectory calculation tool is incorrectly interpreting the vector of the green arrow, leading to a wrong path projection.
4. Next time, consider: A more robust trajectory calculation that correctly identifies the ball center, the arrow vector, and performs accurate geometric reflection off the table rails.
