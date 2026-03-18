---
name: chartqa_case_train_augmented_128_failure_lesson
description: "Lessons on interpreting chart data with numeric precision and currency context."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when processing and interpreting numeric data from charts, especially when currency labels are present or when there is a high risk of misinterpreting numeric details."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image is a bar chart of Sony's net income over fiscal years with values in billion JPY and million USD. Tool-generated images are black and white, emphasizing grid and values but losing some clarity. A new tool for precise extraction will directly address the numeric inconsistency seen in the agent's answers.
3. Common mistake: The existing tools failed to accurately extract numeric values from the chart, leading to inaccurate interpretations.
4. Next time, consider: Precision extraction of numeric values with attention to currency labels.
