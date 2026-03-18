---
name: chartqa_case_train_augmented_127_failure_lesson
description: "Improving extraction of numeric data from charts when dealing with labeled bars."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when working with tasks that require extracting specific numeric values from chart labels or bars, especially when the chart includes financial or non-target related data."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image is a bar chart of Sony's net income over fiscal years. Tool-generated images are black and white with labels, but lack clarity in numeric values. The chart does not contain employment data, making the task unsolvable with existing tools.
3. Common mistake: The existing tools failed to extract the relevant numeric data for Sony's employment figures as the chart shows financial data instead.
4. Next time, consider: Incorporate more detailed numeric label extraction specific to employment figures.
