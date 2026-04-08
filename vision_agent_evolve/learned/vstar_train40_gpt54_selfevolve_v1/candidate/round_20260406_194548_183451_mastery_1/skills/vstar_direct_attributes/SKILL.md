---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_local_color."
level: mid
depends_on: []
applicability_conditions: "Use when the question asks for a directly visible attribute of a specifically named object, accessory, or garment.; Use when the referent may be small or embedded in a cluttered scene and should be localized before judging its color or other simple visual attribute.; Use when multiple-choice options are visually confusable and a local inspection step would reduce answer noise."
        ---

## SOP
1. Confirm this applies: Use when the question asks for a directly visible attribute of a specifically named object, accessory, or garment.; Use when the referent may be small or embedded in a cluttered scene and should be localized before judging its color or other simple visual attribute.; Use when multiple-choice options are visually confusable and a local inspection step would reduce answer noise.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Do not use when the target entity is already obvious at full-image scale and its attribute is unambiguous.; Do not use when the question requires counting, reading text, or comparing several similar objects.; Do not use when the referent cannot be described well enough for object localization.), skip the tool path and answer directly; otherwise answer from the final artifact.
