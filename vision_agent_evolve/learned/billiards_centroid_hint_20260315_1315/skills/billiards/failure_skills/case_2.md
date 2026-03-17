---
name: billiards_case_2_failure_lesson
description: "Failure lesson for geometric trajectory prediction on billiards tables."
level: low
depends_on: []
applicability_conditions: "When the task requires predicting the final pocket of a ball based on a directional vector and rail reflections."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example.
2. Helpful method: A billiards table with a blue ball and a green arrow indicating direction. The arrow points towards the bottom rail. Visual estimation of complex reflection paths is difficult for VLMs; a geometric overlay tool provides the necessary precision.
3. Common mistake: The agent failed to accurately calculate the reflection trajectory of the ball off the rails.
4. Next time, consider: A geometric projection tool that draws the trajectory line based on the ball's position and arrow vector, including reflections.
