---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy region_then_text_zoom."
level: mid
depends_on: []
applicability_conditions: "When the package contains many small regions and the nutrition label location is unclear; When the relevant evidence is localized but may include mixed visual cues such as a nutrition panel, serving icon, or front label that must be found before reading text"
        ---

## SOP
1. Confirm this applies: When the package contains many small regions and the nutrition label location is unclear; When the relevant evidence is localized but may include mixed visual cues such as a nutrition panel, serving icon, or front label that must be found before reading text
2. Run `python -m tools localized_region_zoom <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_text_zoom <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (When the nutrition text region is already obvious enough for direct text zoom; When the task is purely object counting or position reasoning rather than nutrient extraction), skip the tool path and answer directly; otherwise answer from the final artifact.
