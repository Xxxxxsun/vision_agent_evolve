---
name: chartqa_case_train_augmented_16_failure_lesson
description: "Importance of extracting data using visual distinctions in charts."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when processing tasks involving charts that use color or other visual cues to distinguish data categories."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image displays a stacked bar chart with various revenue categories including Subscription and Streaming identified by color. The artifact image lacks these specific color-coding details. A new tool targeting color-coded data extraction will enable accurate reading of chart categories, leading to the correct answer.
3. Common mistake: The tool-generated artifact lost color distinctions necessary to identify Subscription and Streaming revenues accurately.
4. Next time, consider: Extract specific category data from the chart by identifying corresponding color sections.
