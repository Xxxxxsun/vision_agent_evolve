---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy contextual_entity_identification."
level: mid
depends_on: []
applicability_conditions: "The scene is complex with multiple participants (e.g., a stadium or political rally); The event type needs to be established before identifying specific teams"
        ---

## SOP
1. Confirm this applies: The scene is complex with multiple participants (e.g., a stadium or political rally); The event type needs to be established before identifying specific teams
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (The image contains only a single object; The question only requires a count of objects), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
