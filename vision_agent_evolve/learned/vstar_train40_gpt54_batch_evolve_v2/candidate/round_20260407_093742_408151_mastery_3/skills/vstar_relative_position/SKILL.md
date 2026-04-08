---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy zoom_after_localization_if_small."
level: mid
depends_on: []
applicability_conditions: "Use when the queried objects are present but appear small, distant, or easy to miss in the full image.; Use when approximate localization is possible yet confidence in the object identity or center position is low from the original scale.; Use when a magnified local inspection can improve horizontal comparison between two boxes."
        ---

## SOP
1. Confirm this applies: Use when the queried objects are present but appear small, distant, or easy to miss in the full image.; Use when approximate localization is possible yet confidence in the object identity or center position is low from the original scale.; Use when a magnified local inspection can improve horizontal comparison between two boxes.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (Do not use when the objects are already large and clearly separated in the full image.; Do not use when localization itself is highly uncertain or returns many ambiguous candidates.; Do not use when the task depends on global layout beyond the localized regions.), skip the tool path and answer directly; otherwise answer from the final artifact.
