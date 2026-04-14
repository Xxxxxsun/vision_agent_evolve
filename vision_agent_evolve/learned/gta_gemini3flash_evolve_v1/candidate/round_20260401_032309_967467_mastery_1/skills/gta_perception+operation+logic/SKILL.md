---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy multimodal_health_quantifier."
level: mid
depends_on: []
applicability_conditions: "The question requires extracting nutritional data from an image (labels, menus, or fruit types).; The task involves mapping visual data to external health standards or demographic-specific guidelines.; A mathematical conversion or calculation is needed to reach the final answer."
        ---

## SOP
1. Confirm this applies: The question requires extracting nutritional data from an image (labels, menus, or fruit types).; The task involves mapping visual data to external health standards or demographic-specific guidelines.; A mathematical conversion or calculation is needed to reach the final answer.
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (The nutritional information is already provided in the text prompt.; The question asks for a subjective medical diagnosis rather than a quantitative calculation.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
