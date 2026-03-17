---
name: rolling_dice_top_case_2_failure_lesson
description: "Lesson on maintaining accurate dice orientation state during sequential path rotations."
level: low
depends_on: []
applicability_conditions: "Relevant for any task requiring the tracking of a dice's top face after a series of movements along a grid path."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a green dice on a grid with a path indicated by an arrow. The tool-generated artifacts overlay a grid on the image to help track the dice's movement. The grid overlay is helpful, but the agent lacks a formal procedure to maintain the dice's orientation state across multiple steps, leading to cumulative errors.
3. Common mistake: The agent fails to correctly track the state of the dice (top, front, right faces) through the sequence of rotations along the path.
4. Next time, consider: A step-by-step state tracker that explicitly calculates the dice orientation after each rotation in the path.
