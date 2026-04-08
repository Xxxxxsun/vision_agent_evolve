---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy localize_then_compare_horizontal."
level: mid
depends_on: []
applicability_conditions: "Use for left-versus-right questions involving two distinct visible objects named by category or simple attribute cues.; Use when the objects are spatially separated enough that approximate boxes can support a horizontal comparison.; Use when the family question asks for relative position rather than counting, reading text, or fine-grained recognition."
        ---

## SOP
1. Confirm this applies: Use for left-versus-right questions involving two distinct visible objects named by category or simple attribute cues.; Use when the objects are spatially separated enough that approximate boxes can support a horizontal comparison.; Use when the family question asks for relative position rather than counting, reading text, or fine-grained recognition.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Do not use when one or both referenced objects are heavily occluded, truncated, or too ambiguous to localize reliably.; Do not use when the relation depends on depth, overlap ordering, or selecting among many nearly identical instances without a clear referent.; Do not use when the answer requires more than simple horizontal left-right comparison.), skip the tool path and answer directly; otherwise answer from the final artifact.
