---
name: chartqa_case_train_augmented_180_failure_lesson
description: "Improving accuracy in numeric label extraction from bar charts."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when interpreting numeric values from bar charts, especially when agent output and expected numeric values differ, indicating label extraction issues."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image is a bar chart with different colored bars representing retail sales categories over time. The artifact is a black and white version highlighting chart labels but missing numerical details above bars. A new tool focusing on extracting numerical details from chart tops will address the primary obstacle in obtaining accurate answers.
3. Common mistake: The tool failed to capture and read numeric labels at the top of the chart bars correctly.
4. Next time, consider: Accurate extraction of numeric labels at the top of bar charts.
