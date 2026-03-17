---
name: billiards_case_2_failure_lesson
description: "Failure lesson for geometric trajectory prediction in billiards tasks."
level: low
depends_on: []
applicability_conditions: "When the task requires predicting the path of a ball on a billiards table involving reflections off rails."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example.
2. Helpful method: The original image shows a blue ball with a green arrow pointing down-left. The tool-generated artifacts show incorrect, complex, and non-physical reflection paths that do not align with the simple geometry of the ball and arrow. The current tool is failing to perform basic geometric reflection correctly. A new, specialized tool that explicitly calculates the reflection points based on the input vector is required to solve the task.
3. Common mistake: The existing trajectory plotter tool is producing hallucinated, non-physical paths that do not follow the law of reflection (angle of incidence equals angle of reflection).
4. Next time, consider: A reliable geometric reflection calculator that correctly implements the law of reflection on a rectangular boundary.
