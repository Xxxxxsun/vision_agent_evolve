---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy text-first nutrition zoom."
level: mid
depends_on: []
applicability_conditions: "When the answer depends on small nutrition-label text such as sugar, serving size, or per-100ml values.; When the image likely contains a package, bottle, can, or food label with localized numeric text that must be read before arithmetic."
        ---

## SOP
1. Confirm this applies: When the answer depends on small nutrition-label text such as sugar, serving size, or per-100ml values.; When the image likely contains a package, bottle, can, or food label with localized numeric text that must be read before arithmetic.
2. Run `python -m tools localized_text_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (When the needed quantity is already large and clearly legible without magnification.; When the task is primarily object counting or spatial reasoning rather than reading label text.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
