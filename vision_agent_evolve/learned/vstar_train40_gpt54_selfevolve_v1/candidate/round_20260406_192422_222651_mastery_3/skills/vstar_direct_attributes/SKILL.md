---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy bbox_then_zoomed_color_verification."
level: mid
depends_on: []
applicability_conditions: "when the named object can be localized but its color patch is small or subtle; when the object is distant, partially visible, or blended with surrounding colors; when a two-step confirmation is needed before selecting among close color options"
        ---

## SOP
1. Confirm this applies: when the named object can be localized but its color patch is small or subtle; when the object is distant, partially visible, or blended with surrounding colors; when a two-step confirmation is needed before selecting among close color options
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the object occupies a large clear region and zoom is unnecessary; when localization is unreliable because the text description is too vague; when the question is outside direct visible attribute lookup), skip the tool path and answer directly; otherwise answer from the final artifact.
