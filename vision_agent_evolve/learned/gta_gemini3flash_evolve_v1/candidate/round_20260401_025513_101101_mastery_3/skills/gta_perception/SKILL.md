---
name: gta_perception
description: "Mastery SOP for gta_perception using strategy spatial_text_reasoning."
level: mid
depends_on: []
applicability_conditions: "The question asks to identify 'opposing' teams or entities on different sides of a frame; The identification depends on the spatial relationship between two distinct text regions"
        ---

## SOP
1. Confirm this applies: The question asks to identify 'opposing' teams or entities on different sides of a frame; The identification depends on the spatial relationship between two distinct text regions
2. Run `python -m tools relative_position_marker <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_text_zoom <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (There is only one primary subject in the image; The question does not involve comparison or opposition), skip the tool path and answer directly; otherwise answer from the final artifact.
