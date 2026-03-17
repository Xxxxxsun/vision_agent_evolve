---
name: defuse_a_bomb_case_2_failure_lesson
description: "Lesson on tracking continuous paths through visual occlusions in circuit-based puzzles."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires identifying a specific wire connection where segments are hidden by obstacles (e.g., slats, covers, or overlapping components)."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image shows a circuit board with four wires (A, B, C, D) entering from the right, partially obscured by vertical metal slats. The wires zig-zag behind the slats and connect to bomb icons on the left. The task requires precise path following through occlusions. Since the agent has failed multiple times, a dedicated path-tracing tool is necessary to provide the visual clarity required for accurate decision-making.
3. Common mistake: The agent is struggling to visually track the continuous path of the wires through the occlusions caused by the metal slats.
4. Next time, consider: A tool that explicitly traces and highlights the path of each wire from the right terminal to the left connection point.
