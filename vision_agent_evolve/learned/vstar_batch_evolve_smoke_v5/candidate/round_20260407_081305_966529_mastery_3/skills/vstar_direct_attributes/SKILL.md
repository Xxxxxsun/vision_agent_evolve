---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy zoom-before-attribute."
level: mid
depends_on: []
applicability_conditions: "when the named object can be localized but appears small or visually ambiguous; when a fine-grained local inspection is needed after finding the object; when color judgment may be affected by scale, clutter, or overlapping items"
        ---

## SOP
1. Confirm this applies: when the named object can be localized but appears small or visually ambiguous; when a fine-grained local inspection is needed after finding the object; when color judgment may be affected by scale, clutter, or overlapping items
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the object is large and clearly visible without magnification; when the question can be answered by direct scene inspection alone; when the task is not a localized visual attribute lookup), skip the tool path and answer directly; otherwise answer from the final artifact.
