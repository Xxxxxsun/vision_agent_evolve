---
name: chartqa
description: "Minimal skill for ChartQA — tools-first"
level: mid
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image", "execute_python"]
final_answer_policy: direct_answer
applicability_conditions: "Use for ChartQA questions about chart values, comparisons, or text labels."
---

# ChartQA

Zoom into the chart region containing the relevant bar, line, label, or legend entry.
Extract the numeric value, then use execute_python if arithmetic is needed.
Return the numeric or text answer directly — do not return an option letter.
