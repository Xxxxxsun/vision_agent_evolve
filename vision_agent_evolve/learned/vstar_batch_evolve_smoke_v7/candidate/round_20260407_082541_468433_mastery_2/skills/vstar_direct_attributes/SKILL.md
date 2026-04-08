---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_evidence_first_then_local_read."
level: mid
depends_on: []
applicability_conditions: "Use when the task is a direct color-identification question about one salient object; Use when color is the discriminative attribute and the object may be small, partially occluded, or embedded in clutter; Use when family-level failures suggest missed local color evidence rather than lack of object vocabulary"
        ---

## SOP
1. Confirm this applies: Use when the task is a direct color-identification question about one salient object; Use when color is the discriminative attribute and the object may be small, partially occluded, or embedded in clutter; Use when family-level failures suggest missed local color evidence rather than lack of object vocabulary
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the question is not about color or another short local visual attribute; Avoid when the object category itself is uncertain and needs explicit localization by name first; Avoid when the answer requires global scene understanding rather than local evidence), skip the tool path and answer directly; otherwise answer from the final artifact.
