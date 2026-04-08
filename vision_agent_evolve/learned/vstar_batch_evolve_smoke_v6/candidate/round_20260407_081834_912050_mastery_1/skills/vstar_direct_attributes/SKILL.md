---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_read_local_color."
level: mid
depends_on: []
applicability_conditions: "when the question asks for the color of a specifically named object or clothing item; when the target object must be localized by noun phrase before its attribute can be inspected; when answer options are color words and the task is direct visual lookup"
        ---

## SOP
1. Confirm this applies: when the question asks for the color of a specifically named object or clothing item; when the target object must be localized by noun phrase before its attribute can be inspected; when answer options are color words and the task is direct visual lookup
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the question requires counting, reading text, or relational reasoning instead of local attribute inspection; when the target object is already unambiguous and large enough to inspect without localization; when the object description is too vague to localize reliably), skip the tool path and answer directly; otherwise answer from the final artifact.
