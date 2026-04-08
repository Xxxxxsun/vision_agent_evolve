---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy locate_then_compare_position."
level: mid
depends_on: []
applicability_conditions: "when the question asks for left/right or above/below relation between two named objects; when both target entities are likely visually distinct enough to localize from text descriptions; when direct inspection is uncertain because multiple objects or cluttered scenes make spatial comparison easy to miss"
        ---

## SOP
1. Confirm this applies: when the question asks for left/right or above/below relation between two named objects; when both target entities are likely visually distinct enough to localize from text descriptions; when direct inspection is uncertain because multiple objects or cluttered scenes make spatial comparison easy to miss
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when one or both referenced entities are too ambiguous to localize reliably by name alone; when the task depends on depth, occlusion, or front/behind rather than 2D image position; when the image is already simple enough that the relation is obvious without tooling), skip the tool path and answer directly; otherwise answer from the final artifact.
