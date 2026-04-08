---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy scene_scan_then_localize."
level: mid
depends_on: []
applicability_conditions: "when the scene is cluttered, unusual, illustrated, or contains many candidate objects with similar appearance; when object names may need light scene grounding before localization; when a brief whole-image understanding can improve later object targeting for relative-position comparison"
        ---

## SOP
1. Confirm this applies: when the scene is cluttered, unusual, illustrated, or contains many candidate objects with similar appearance; when object names may need light scene grounding before localization; when a brief whole-image understanding can improve later object targeting for relative-position comparison
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the image is simple and the two objects can likely be localized immediately; when the question depends on fine-grained text reading rather than object position; when the task is outside the family's supported left/right or above/below comparison), skip the tool path and answer directly; otherwise answer from the final artifact.
