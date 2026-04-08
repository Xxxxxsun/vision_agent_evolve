---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy mark-and-judge-relative-position."
level: mid
depends_on: []
applicability_conditions: "Use for left/right or above/below questions when the image is cluttered or the two target objects are small but still salient.; Use when explicit spatial annotation would reduce mistakes from informal visual inspection."
        ---

## SOP
1. Confirm this applies: Use for left/right or above/below questions when the image is cluttered or the two target objects are small but still salient.; Use when explicit spatial annotation would reduce mistakes from informal visual inspection.
2. Run `python -m tools relative_position_marker <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (Do not use for non-spatial questions or when the relation depends on text labels, counts, or hidden/occluded objects.; Avoid when one of the target objects cannot be visually grounded at all.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
