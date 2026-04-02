---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy region-then-text drilldown."
level: mid
depends_on: []
applicability_conditions: "When the relevant evidence is small and its exact location is unclear, such as a busy package with multiple panels.; When a nutrition table may be present but first needs generic region localization before text reading."
        ---

## SOP
1. Confirm this applies: When the relevant evidence is small and its exact location is unclear, such as a busy package with multiple panels.; When a nutrition table may be present but first needs generic region localization before text reading.
2. Run `python -m tools localized_region_zoom <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_text_zoom <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (When the nutrition panel is already obvious and only magnification is needed.; When the image lacks any package-like or label-like region.), skip the tool path and answer directly; otherwise answer from the final artifact.
