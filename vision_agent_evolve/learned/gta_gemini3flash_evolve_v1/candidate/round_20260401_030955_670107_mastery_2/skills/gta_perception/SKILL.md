---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy Multi-Modal Visual Verification."
level: mid
depends_on: []
applicability_conditions: "Question requires identifying teams based on logos, colors, or specific equipment rather than just text; The target object is small and requires magnification to distinguish between similar visual attributes"
        ---

## SOP
1. Confirm this applies: Question requires identifying teams based on logos, colors, or specific equipment rather than just text; The target object is small and requires magnification to distinguish between similar visual attributes
2. Run `python -m tools localized_region_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (The question is purely about reading a specific word or number; The image resolution is high enough to see all details clearly), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
