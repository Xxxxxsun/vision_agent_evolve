---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_focus_then_local_check."
level: mid
depends_on: []
applicability_conditions: "when the question is a multiple-choice direct-attribute item asking for a local object's color; when the target may be visually salient but easy to confuse with nearby similarly colored items; when a lightweight region-focusing pass can surface the most discriminative color evidence"
        ---

## SOP
1. Confirm this applies: when the question is a multiple-choice direct-attribute item asking for a local object's color; when the target may be visually salient but easy to confuse with nearby similarly colored items; when a lightweight region-focusing pass can surface the most discriminative color evidence
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the object identity itself is ambiguous and must first be explicitly localized from language; when the question is about text content, counting, or relations rather than color; when the color evidence is already unmistakable at full-image scale), skip the tool path and answer directly; otherwise answer from the final artifact.
