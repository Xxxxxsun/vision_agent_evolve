---
name: hrbench
description: "Minimal skill for HRBench — tools-first"
level: mid
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image"]
final_answer_policy: option_letter
applicability_conditions: "Use for HRBench multiple-choice questions about local text, signs, or symbols."
---

# HRBench

Zoom into the region where the target text or symbol appears (set center_x/center_y to its location).
Use crop_image if the zoomed region is still cluttered.
Return the matching option letter.
