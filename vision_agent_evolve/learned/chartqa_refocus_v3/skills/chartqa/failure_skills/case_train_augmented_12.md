---
name: chartqa_case_train_augmented_12_failure_lesson
description: "Ensure accurate numerical extraction from detailed chart data."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when an agent is tasked with extracting precise numerical values from visual data like charts or graphs, especially when those values are closely spaced or similar in appearance."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Use the validated tool output to answer this task family.
3. Common mistake: The agent misread the numerical value due to the close proximity of similar numbers.
4. Next time, consider: Implement a precise numerical extraction tool focusing on accurate OCR for closely spaced values in charts.
