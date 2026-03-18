---
name: chartqa_case_train_augmented_12_failure_lesson
description: "Ensuring precise data extraction from visual charts in QA tasks."
level: low
depends_on: []
applicability_conditions: "When dealing with questions that require interpreting data directly from visual sources, such as charts or graphs."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Bar chart showing population of Romania by year with values above each bar. A custom tool for OCR can help extract exact values directly from the image, reducing misinterpretations.
3. Common mistake: Use the validated tool output to answer this task family.
4. Next time, consider: Accurate OCR or image reading to extract values directly from the image.
