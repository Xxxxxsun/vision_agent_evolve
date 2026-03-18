---
name: chartqa_case_train_augmented_96_failure_lesson
description: "Focus on direct text extraction and verification in chart images."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when the task involves interpreting and extracting specific numeric labels from chart images where tool output is losing detail."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image has a bar chart showing number of employees with labels and bars; tool outputs lose color and some text. Extracting exact numeric values from well-defined bars is feasible with a tailored tool.
3. Common mistake: Use the validated tool output to answer this task family.
4. Next time, consider: Use the validated tool output to answer this task family.
