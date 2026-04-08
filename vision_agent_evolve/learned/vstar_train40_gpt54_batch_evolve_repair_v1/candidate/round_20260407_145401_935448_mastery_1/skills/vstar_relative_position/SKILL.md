---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy localize-both-then-compare."
level: mid
depends_on: []
applicability_conditions: "when the question asks whether one named object is left or right of another named object; when both entities are expected to be visible as identifiable objects in a natural image; when baseline failures come from not explicitly localizing the compared objects"
        ---

## SOP
1. Confirm this applies: when the question asks whether one named object is left or right of another named object; when both entities are expected to be visible as identifiable objects in a natural image; when baseline failures come from not explicitly localizing the compared objects
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when one or both referenced entities are too ambiguous to localize reliably from text alone; when the relation depends on heavy occlusion handling or inferred 3D orientation rather than image-plane left/right; when the question is about attributes, counting, or reading text instead of spatial comparison), skip the tool path and answer directly; otherwise answer from the final artifact.
