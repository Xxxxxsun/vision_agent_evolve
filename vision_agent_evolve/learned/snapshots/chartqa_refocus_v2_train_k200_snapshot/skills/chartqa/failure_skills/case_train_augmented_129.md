---
name: chartqa_case_train_augmented_129_failure_lesson
description: "Improve precision in extracting numeric values from charts to avoid misinterpretations."
level: low
depends_on: []
applicability_conditions: "Use this lesson when interpreting numeric data from charts, especially bar charts, and when numeric extraction might lead to approximations."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image is a bar chart showing imports in billion U.S. dollars over time. Tool-generated artifacts failed to extract numeric values or were blank. The agent's answer reflects a failure to extract correct values, indicating a need for improved numeric extraction capabilities.
3. Common mistake: The agent misinterpreted the numeric values in the chart, leading to an incorrect answer.
4. Next time, consider: Precise extraction of numeric values from chart bars.
