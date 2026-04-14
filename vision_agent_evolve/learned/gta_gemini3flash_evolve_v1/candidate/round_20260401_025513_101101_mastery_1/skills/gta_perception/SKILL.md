---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy high_precision_text_extraction."
level: mid
depends_on: []
applicability_conditions: "The question asks for specific names, teams, or events; The image contains small-scale text on jerseys, banners, or scoreboards; Standard OCR is likely to miss high-entropy identifiers"
        ---

## SOP
1. Confirm this applies: The question asks for specific names, teams, or events; The image contains small-scale text on jerseys, banners, or scoreboards; Standard OCR is likely to miss high-entropy identifiers
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (The text is large and clearly legible in the original image; The question is about abstract visual concepts rather than specific entities), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
