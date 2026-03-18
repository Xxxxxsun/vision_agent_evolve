---
name: chartqa_case_train_augmented_179_failure_lesson
description: "Improve numeric data extraction from chart bars for accurate answers in ChartQA tasks."
level: low
depends_on: []
applicability_conditions: "Relevant for instances where numeric extraction is required from chart bars, especially when numeric labels are at the top or not clearly visible."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Use the validated tool output to answer this task family.
3. Common mistake: Failed numeric extraction from top of bars; tool did not capture required details for accurate answer.
4. Next time, consider: Improve numeric label extraction specifically for top of bars indicating total retail sales change.
