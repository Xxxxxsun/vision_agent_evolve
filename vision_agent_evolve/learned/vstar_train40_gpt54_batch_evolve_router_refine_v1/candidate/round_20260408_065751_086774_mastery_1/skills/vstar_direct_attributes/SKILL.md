---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy localize_then_inspect_color."
level: mid
depends_on: []
applicability_conditions: "when the question asks for the color of a named object, accessory, or clothing item visible in the image; when the target item is likely small or attached to a person and global inspection may miss its true color; when success depends on isolating one referenced region before judging color"
        ---

## SOP
1. Confirm this applies: when the question asks for the color of a named object, accessory, or clothing item visible in the image; when the target item is likely small or attached to a person and global inspection may miss its true color; when success depends on isolating one referenced region before judging color
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the question depends on reading text, numbers, or labels; when the target object is extremely obvious and occupies a large distinctive region, making localization unnecessary; when the asked attribute is not a visible local attribute), skip the tool path and answer directly; otherwise answer from the final artifact.
