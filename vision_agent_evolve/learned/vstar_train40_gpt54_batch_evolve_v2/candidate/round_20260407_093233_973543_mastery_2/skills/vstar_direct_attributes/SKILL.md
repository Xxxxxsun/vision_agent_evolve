---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_first_local_focus."
level: mid
depends_on: []
applicability_conditions: "when the task is a direct color question about a single object and discriminative evidence is expected to be local; when the object may be small, partially occluded, or easy to miss without color-oriented attention; when candidate answers are a small set of basic colors"
        ---

## SOP
1. Confirm this applies: when the task is a direct color question about a single object and discriminative evidence is expected to be local; when the object may be small, partially occluded, or easy to miss without color-oriented attention; when candidate answers are a small set of basic colors
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the target must first be identified by reading text or by complex relations; when the object category itself is unclear and needs explicit localization before attribute reading; when the question asks about attributes beyond localized appearance), skip the tool path and answer directly; otherwise answer from the final artifact.
