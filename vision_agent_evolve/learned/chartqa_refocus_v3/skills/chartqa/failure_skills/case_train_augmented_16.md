---
name: chartqa_case_train_augmented_16_failure_lesson
description: "Failure lesson on handling numerical extraction from visually complex charts."
level: low
depends_on: []
applicability_conditions: "Applicable when interpreting and extracting data from multi-segment color-coded charts."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Use the validated tool output to answer this task family.
3. Common mistake: The agent failed to accurately extract the numerical value for the 'Subscription and streaming' segment due to the complexity of similarly colored segments.
4. Next time, consider: Implement a tool for precise OCR targeting the specific color-coded segments for accurate numerical extraction.
