---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy localized_color_assist."
level: mid
depends_on: []
applicability_conditions: "Use for direct attribute questions where the answer is a local color and the relevant item may be small, partially occluded, or visually cluttered.; Use when the object mention is straightforward but the main difficulty is isolating discriminative color evidence rather than identifying the whole scene.; Use when multiple-choice options are color names and a focused local inspection would reduce confusion."
        ---

## SOP
1. Confirm this applies: Use for direct attribute questions where the answer is a local color and the relevant item may be small, partially occluded, or visually cluttered.; Use when the object mention is straightforward but the main difficulty is isolating discriminative color evidence rather than identifying the whole scene.; Use when multiple-choice options are color names and a focused local inspection would reduce confusion.
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Do not use when the target cannot be approximately grounded from the question at all.; Do not use when the attribute requested is not color or not a short local visual property.; Do not use when the image is simple and the target color is obvious without extra processing.), skip the tool path and answer directly; otherwise answer from the final artifact.
