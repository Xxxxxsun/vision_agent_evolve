---
name: chartqa_case_train_augmented_126_failure_lesson
description: "Lessons on improving interpretation of numeric values in charts for better accuracy in answers."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant when dealing with questions requiring extraction of numeric values from charts, especially when these values might be presented in different currencies or units."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The original image shows a bar chart with values in both yen and USD. The tool-generated artifacts are black and white with visible labels but lost clarity in numeric values. A targeted tool will address the currency differentiation, aiding precise extraction of relevant values.
3. Common mistake: The agent failed due to incorrect numeric extraction from the chart, leading to an inaccurate interpretation.
4. Next time, consider: Improved numeric extraction and interpretation focusing on currency differentiation.
