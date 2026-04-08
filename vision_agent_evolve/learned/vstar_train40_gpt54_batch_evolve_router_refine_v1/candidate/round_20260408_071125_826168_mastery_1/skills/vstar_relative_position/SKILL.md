---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy locate-and-compare-horizontal-order."
level: mid
depends_on: []
applicability_conditions: "when the prompt asks whether one named object is left or right of another named object in a natural image; when both referenced objects are expected to be visually present and separable enough to localize; when the relation can be decided by comparing horizontal positions of the two localized objects"
        ---

## SOP
1. Confirm this applies: when the prompt asks whether one named object is left or right of another named object in a natural image; when both referenced objects are expected to be visually present and separable enough to localize; when the relation can be decided by comparing horizontal positions of the two localized objects
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when either referenced object is too ambiguous to localize from text alone; when the answer would require depth, viewpoint, or occlusion reasoning rather than simple 2D horizontal comparison; when one or both objects are not visible enough for reliable localization), skip the tool path and answer directly; otherwise answer from the final artifact.
