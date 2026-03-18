---
name: chartqa_case_train_augmented_97_failure_lesson
description: "Improve clarity and accuracy in extracting numeric values from chart images."
level: low
depends_on: []
applicability_conditions: "This lesson is relevant for tasks involving reading numeric values and labels from chart images, especially when dealing with converted or artifact images where color and detail might be lost."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: Original image is a bar chart showing number of employees per year with clear labels. Tool-generated images are black and white, losing color and some text, reducing readability. A tool update will directly address the clarity and accuracy issues, helping extract correct values.
3. Common mistake: The agent failed to extract exact numeric values correctly due to lost context in the black and white artifact images.
4. Next time, consider: Need a tool to enhance numeric value clarity and readability from current artifacts.
