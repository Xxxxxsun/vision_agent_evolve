---
name: chartqa_case_train_augmented_29_failure_lesson
description: "Challenges in interpreting stacked bar charts accurately."
level: low
depends_on: []
applicability_conditions: "Applicable when interpreting stacked bar charts with multiple colored segments corresponding to different categories or regions."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image shows a stacked bar chart with revenue by region. Tool artifacts lost color and detailed segment information. Existing tools failed to capture segment details; a specialized tool is essential to extract accurate data.
3. Common mistake: Agent could not accurately extract specific colored segment to determine the precise value.
4. Next time, consider: Accurate extraction of specific colored segments from stacked bar chart.
