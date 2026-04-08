---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy ground_then_local_color."
level: mid
depends_on: []
applicability_conditions: "Use for direct multiple-choice visual questions asking for the color of a specifically named object or object part.; Use when the referenced target is localizable from the noun phrase in the question and the answer depends on inspecting that single region.; Use when there may be many objects in the scene and the model should first ground the target before reading its attribute."
        ---

## SOP
1. Confirm this applies: Use for direct multiple-choice visual questions asking for the color of a specifically named object or object part.; Use when the referenced target is localizable from the noun phrase in the question and the answer depends on inspecting that single region.; Use when there may be many objects in the scene and the model should first ground the target before reading its attribute.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Do not use when the task is counting, comparison, or broader scene reasoning rather than a single localized attribute.; Do not use when the reference is too ambiguous among multiple similar instances and the question provides no clear disambiguation.; Do not use when the target is already unmistakably central and large enough for direct answering without localization overhead.), skip the tool path and answer directly; otherwise answer from the final artifact.
