---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy scene-scan-then-target-localize."
level: mid
depends_on: []
applicability_conditions: "when the image is cluttered, visually complex, or the target object names may be ambiguous without scene context; when a quick global scene read can help confirm the intended referents before localization; when left/right judgment is simple once the correct two entities are identified"
        ---

## SOP
1. Confirm this applies: when the image is cluttered, visually complex, or the target object names may be ambiguous without scene context; when a quick global scene read can help confirm the intended referents before localization; when left/right judgment is simple once the correct two entities are identified
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the scene is simple and direct localization is likely sufficient; when the image description would add little value because the two targets are already explicit and salient; when the task is not about horizontal relative position), skip the tool path and answer directly; otherwise answer from the final artifact.
