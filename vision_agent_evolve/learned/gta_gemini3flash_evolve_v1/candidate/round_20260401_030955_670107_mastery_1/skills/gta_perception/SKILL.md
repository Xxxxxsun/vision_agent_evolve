---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy Text-Centric Entity Identification."
level: mid
depends_on: []
applicability_conditions: "Question asks for specific names of teams, events, or sponsors; Identifying information is likely contained in small text on jerseys, scoreboards, or banners; Global image view is insufficient to read fine-grained alphanumeric characters"
        ---

## SOP
1. Confirm this applies: Question asks for specific names of teams, events, or sponsors; Identifying information is likely contained in small text on jerseys, scoreboards, or banners; Global image view is insufficient to read fine-grained alphanumeric characters
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (The question can be answered by identifying broad visual categories (e.g., 'soccer', 'basketball'); No text is visible in the scene), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
