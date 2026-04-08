---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_evidence_first_then_local_attribute."
level: mid
depends_on: []
applicability_conditions: "Use for direct attribute questions where the answer options are mostly colors and the likely failure mode is missing the discriminative colored patch.; Use when the object may be small, partially occluded, or visually blended with nearby items, so color-salient candidate regions help before final reading.; Use across family cases involving named objects or clothing belonging to a referenced subject."
        ---

## SOP
1. Confirm this applies: Use for direct attribute questions where the answer options are mostly colors and the likely failure mode is missing the discriminative colored patch.; Use when the object may be small, partially occluded, or visually blended with nearby items, so color-salient candidate regions help before final reading.; Use across family cases involving named objects or clothing belonging to a referenced subject.
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the question is not about a local attribute or when color is not a plausible queried attribute.; Avoid when the scene contains many similarly colored small regions and there is no clear textual reference to tie the target down.; Avoid when object localization by name is likely easier and more precise than generic color-focused highlighting.), skip the tool path and answer directly; otherwise answer from the final artifact.
