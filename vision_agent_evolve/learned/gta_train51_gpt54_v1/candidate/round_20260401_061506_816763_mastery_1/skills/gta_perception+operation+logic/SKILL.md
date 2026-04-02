---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy zoom_text_then_scale."
level: mid
depends_on: []
applicability_conditions: "When the question asks for nutrient amount from packaged food/drink and the needed value is likely printed in small nutrition text or front-of-pack text; When the task requires reading a per-serving or per-volume sugar value and then scaling to a stated total quantity such as 500 ml"
        ---

## SOP
1. Confirm this applies: When the question asks for nutrient amount from packaged food/drink and the needed value is likely printed in small nutrition text or front-of-pack text; When the task requires reading a per-serving or per-volume sugar value and then scaling to a stated total quantity such as 500 ml
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (When no readable package text is visible and the item identity must instead be inferred visually for external reference lookup; When the evidence is a chart or non-text visual rather than localized packaging text), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
