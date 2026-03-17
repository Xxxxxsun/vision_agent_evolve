---
name: mirror_pattern_case_1_failure_lesson
description: "Failure lesson for identifying mirrored patterns in complex visual stimuli."
level: low
depends_on: []
applicability_conditions: "When the task requires identifying a mirrored version of a complex, high-detail image (e.g., mandalas, intricate geometric patterns) among multiple similar-looking options."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image contains a complex, radially symmetric mandala pattern labeled and four options (A, B, C, D). The mandala has intricate, non-symmetric color distributions within its segments. The mandala is highly symmetric but contains specific color patterns that are hard to track visually. A programmatic flip and comparison tool will eliminate ambiguity.
3. Common mistake: The agent failed to perform a precise pixel-level comparison between the original mandala and the options, likely due to the high visual complexity and subtle color variations that make manual visual matching difficult.
4. Next time, consider: A tool to perform a horizontal or vertical flip of the original image and compute a difference map (or side-by-side comparison) with the options.
