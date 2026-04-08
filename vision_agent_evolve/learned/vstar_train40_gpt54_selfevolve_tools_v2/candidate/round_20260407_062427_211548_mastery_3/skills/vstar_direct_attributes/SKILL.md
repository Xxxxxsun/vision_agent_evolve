---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy zoom_for_small_local_evidence."
level: mid
depends_on: []
applicability_conditions: "Use when the named object's color evidence is likely very small, distant, or visually cluttered; Use when initial localization is possible but local inspection may still be unreliable at normal scale; Use when fine-grained local viewing is needed to distinguish among similar answer-choice colors"
        ---

## SOP
1. Confirm this applies: Use when the named object's color evidence is likely very small, distant, or visually cluttered; Use when initial localization is possible but local inspection may still be unreliable at normal scale; Use when fine-grained local viewing is needed to distinguish among similar answer-choice colors
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (Avoid when the object is large and clear enough for direct color inspection; Avoid when the image does not permit stable localization of the named object; Avoid when the question is not fundamentally a local visual attribute lookup), skip the tool path and answer directly; otherwise answer from the final artifact.
