---
name: vstar_direct_attributes
description: "Minimal skill for VStar local attribute questions — tools-first"
level: mid
depends_on: ["vstar"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image"]
final_answer_policy: option_letter
applicability_conditions: "Use when the question asks about color or material of one named object."
---

# VStar Direct Attributes

Zoom to the target object's location using center_x/center_y (estimate where it is in the image).
Inspect the color or material attribute in the zoomed view.
Return the matching option letter.
