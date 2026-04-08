---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_check_color."
level: mid
depends_on: []
applicability_conditions: "Use when the question asks for the color of a specifically named object in a natural image; Use when the target object is explicit in the question and may occupy only a local region; Use for direct multiple-choice visual attribute questions where the main challenge is isolating the correct object before judging color"
        ---

## SOP
1. Confirm this applies: Use when the question asks for the color of a specifically named object in a natural image; Use when the target object is explicit in the question and may occupy only a local region; Use for direct multiple-choice visual attribute questions where the main challenge is isolating the correct object before judging color
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the question depends on reading text or symbols; Avoid when the task requires counting, comparison across many objects, or relational reasoning; Avoid when the object is already unambiguous and large enough to judge confidently without localization), skip the tool path and answer directly; otherwise answer from the final artifact.
