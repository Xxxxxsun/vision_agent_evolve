---
name: mirror_pattern_case_1_failure_lesson
description: "Failure lesson for identifying mirrored patterns in complex geometric images."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires identifying a mirrored version of a complex, symmetrical, or highly detailed image among multiple options."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image contains a complex, highly symmetrical mandala pattern labeled and four options (A, B, C, D). The mandala is too complex for visual inspection alone; a programmatic mirror transformation is required to identify the correct option.
3. Common mistake: The agent failed to perform a precise pixel-wise comparison or geometric transformation to detect subtle asymmetries in the mandala patterns.
4. Next time, consider: A tool to perform horizontal or vertical mirroring of the image to compare against the options.
