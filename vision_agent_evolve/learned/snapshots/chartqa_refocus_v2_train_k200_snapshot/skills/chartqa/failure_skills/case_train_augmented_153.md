---
name: chartqa_case_train_augmented_153_failure_lesson
description: "Handling numeric value extraction from bar charts for questions on data points."
level: low
depends_on: []
applicability_conditions: "Applicable when dealing with questions requiring precise numeric extraction from bar chart visuals."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image is a bar chart showing the number of available apps over time. The artifact images attempt to extract labels and bar values but lack clear numeric details for precise extraction. A new tool is needed as current tools do not provide accurate numeric data extraction.
3. Common mistake: The tool failed to accurately extract exact numeric values from the bar heights and labels in the chart.
4. Next time, consider: Precise numeric value extraction directly from bar heights.
