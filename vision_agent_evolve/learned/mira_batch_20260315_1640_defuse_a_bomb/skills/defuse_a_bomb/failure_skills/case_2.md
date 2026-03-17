---
name: defuse_a_bomb_case_2_failure_lesson
description: "Strategy for tracing obscured paths in complex circuit diagrams."
level: low
depends_on: []
applicability_conditions: "When the task requires identifying a continuous path (like a wire) that is partially hidden by obstacles or structural elements."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image shows a circuit board with four wires (A, B, C, D) partially obscured by vertical metal slats. The wires zig-zag between the slats, connecting to bomb icons on the left. Tracing complex, partially hidden paths is a high-error task for VLMs. Providing a tool to isolate and highlight specific paths reduces cognitive load and visual ambiguity.
3. Common mistake: The agent failed to accurately trace the path of the wires through the obscured sections, likely due to the complexity of the zig-zag patterns.
4. Next time, consider: A visual path-tracing tool that highlights or isolates individual wire segments to assist in tracking them across the slats.
