---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy localize-both-then-compare-horizontal."
level: mid
depends_on: []
applicability_conditions: "when the question asks whether one named object is to the left or right of another named object in a single image; when both target entities are concrete visible objects or regions that can be localized; when a lightweight spatial comparison is needed after finding the two referents"
        ---

## SOP
1. Confirm this applies: when the question asks whether one named object is to the left or right of another named object in a single image; when both target entities are concrete visible objects or regions that can be localized; when a lightweight spatial comparison is needed after finding the two referents
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the relation asked is front/behind, depth-based, or otherwise not reducible to horizontal image position; when one or both entities are too abstract or ungroundable for text-based localization; when the answer depends on multi-step reasoning beyond comparing two localized targets), skip the tool path and answer directly; otherwise answer from the final artifact.
