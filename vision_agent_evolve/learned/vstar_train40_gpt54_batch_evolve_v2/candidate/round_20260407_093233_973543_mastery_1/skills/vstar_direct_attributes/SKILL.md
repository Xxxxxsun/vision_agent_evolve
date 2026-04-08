---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_inspect_color."
level: mid
depends_on: []
applicability_conditions: "when the question asks for the color of a specifically named object in the image; when the target object may be moderately localized and not guaranteed to be central or most salient; when multiple-choice options are color names and the task is direct attribute lookup"
        ---

## SOP
1. Confirm this applies: when the question asks for the color of a specifically named object in the image; when the target object may be moderately localized and not guaranteed to be central or most salient; when multiple-choice options are color names and the task is direct attribute lookup
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the question requires counting, reading text, or relational reasoning instead of object color; when the named object is too ambiguous to localize from text alone; when the answer depends on scene-wide color context rather than a single object), skip the tool path and answer directly; otherwise answer from the final artifact.
