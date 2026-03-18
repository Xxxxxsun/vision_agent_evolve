---
name: chartqa_case_train_augmented_161_failure_lesson
description: "Addressing misinterpretation of numeric labels in bar charts."
level: low
depends_on: []
applicability_conditions: "This lesson applies when interpreting numeric labels on bar charts, specifically values at the top of bars which may not be extracted properly."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image shows a bar chart with two sets of numbers inside each bar. Tool-generated image highlights labels but is missing clarity in top numeric labels. Missing numeric extraction from top of bars led to incorrect answers; improving this will address the core problem.
3. Common mistake: The tool did not extract both sets of numeric labels clearly, especially the values on top of each bar.
4. Next time, consider: Extract numeric data on top of each bar more clearly.
