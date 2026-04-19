---
name: vstar_relative_position
description: "Minimal skill for VStar spatial relation questions — tools-first"
level: mid
depends_on: ["vstar"]
tool_names: ["list_images", "get_image_info", "zoom_image"]
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks about left/right/above/below relation between two objects."
---

# VStar Relative Position

If an object is hard to localize, zoom to its estimated position (center_x/center_y).
Judge left/right from the viewer's perspective using the full image as the reference frame.
Return the matching option letter — never let a zoomed view replace the full-image spatial frame.
