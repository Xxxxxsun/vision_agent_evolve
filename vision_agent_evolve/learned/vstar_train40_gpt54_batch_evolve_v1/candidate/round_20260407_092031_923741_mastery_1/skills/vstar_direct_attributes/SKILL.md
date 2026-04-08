---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy localize_then_read_color."
level: mid
depends_on: []
applicability_conditions: "when the question asks for the color of a specifically named object in the image; when the target object may be small, off-center, or one of several objects; when success depends on isolating the referenced object before judging its dominant color"
        ---

## SOP
1. Confirm this applies: when the question asks for the color of a specifically named object in the image; when the target object may be small, off-center, or one of several objects; when success depends on isolating the referenced object before judging its dominant color
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the object is already unambiguous and large enough to identify and inspect without tooling; when the question asks for text, brand, material, or pattern rather than basic color; when the named object is not visually present or cannot be localized reliably), skip the tool path and answer directly; otherwise answer from the final artifact.
