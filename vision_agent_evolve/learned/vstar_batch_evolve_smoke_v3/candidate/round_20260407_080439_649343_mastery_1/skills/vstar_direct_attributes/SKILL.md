---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_read_local_color."
level: mid
depends_on: []
applicability_conditions: "Use for direct multiple-choice questions asking for the color of a named, localized object or accessory in the image; Use when the target object is visually present but small enough that whole-image inspection may miss its color; Use when the object can be described in text well enough to localize before attribute reading"
        ---

## SOP
1. Confirm this applies: Use for direct multiple-choice questions asking for the color of a named, localized object or accessory in the image; Use when the target object is visually present but small enough that whole-image inspection may miss its color; Use when the object can be described in text well enough to localize before attribute reading
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Do not use when the question requires counting, relative position reasoning, or reading embedded text; Do not use when the object occupies a large, obvious portion of the image and direct inspection is sufficient; Do not use when localization is likely ambiguous across many identical instances without extra disambiguation), skip the tool path and answer directly; otherwise answer from the final artifact.
