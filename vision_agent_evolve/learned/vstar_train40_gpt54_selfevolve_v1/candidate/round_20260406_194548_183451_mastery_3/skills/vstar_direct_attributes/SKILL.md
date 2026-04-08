---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy zoom_after_rough_localization."
level: mid
depends_on: []
applicability_conditions: "Use when the named object is likely small, partially occluded, or visually ambiguous in the full image.; Use when direct color judgment may be unreliable unless the local region is magnified.; Use when the question still asks for a single direct visible attribute after localization."
        ---

## SOP
1. Confirm this applies: Use when the named object is likely small, partially occluded, or visually ambiguous in the full image.; Use when direct color judgment may be unreliable unless the local region is magnified.; Use when the question still asks for a single direct visible attribute after localization.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (Do not use when the target is large and clearly visible already.; Do not use when a simple one-step color focus is enough.; Do not use for questions requiring relational reasoning or reading text inside the object.), skip the tool path and answer directly; otherwise answer from the final artifact.
