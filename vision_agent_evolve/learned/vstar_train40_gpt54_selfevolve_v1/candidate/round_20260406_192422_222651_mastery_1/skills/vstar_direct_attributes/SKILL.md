---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_local_color_check."
level: mid
depends_on: []
applicability_conditions: "when the question asks for the color of a specifically named object or clothing item; when the target entity may not be central or may compete with other colorful objects; when a reliable object name is given and localization is likely easier than global inspection"
        ---

## SOP
1. Confirm this applies: when the question asks for the color of a specifically named object or clothing item; when the target entity may not be central or may compete with other colorful objects; when a reliable object name is given and localization is likely easier than global inspection
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the target object is already obvious and large enough to inspect directly; when the image is too cluttered for confident single-object localization from the text description; when the question requires counting, reading text, or multi-step relation reasoning rather than direct attribute lookup), skip the tool path and answer directly; otherwise answer from the final artifact.
