---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate-then-color."
level: mid
depends_on: []
applicability_conditions: "when the question asks for the color of a specifically named object in the image; when the object must first be localized before judging its local visual attribute; when multiple-choice options are color names and the target object reference is visually grounded"
        ---

## SOP
1. Confirm this applies: when the question asks for the color of a specifically named object in the image; when the object must first be localized before judging its local visual attribute; when multiple-choice options are color names and the target object reference is visually grounded
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the object is already unambiguous and large enough to inspect without localization help; when the question depends on reading text, counting, or non-visual world knowledge; when the referenced object cannot be localized reliably from the description), skip the tool path and answer directly; otherwise answer from the final artifact.
