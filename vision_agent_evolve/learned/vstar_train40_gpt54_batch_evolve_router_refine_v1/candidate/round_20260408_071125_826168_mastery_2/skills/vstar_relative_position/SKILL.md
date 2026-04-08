---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy describe-scene-then-localize."
level: mid
depends_on: []
applicability_conditions: "when object names may be broad, unusual, or visually confusable and a quick scene summary can disambiguate them; when the image contains multiple candidate instances and extra context helps identify the intended pair; when a natural-image left/right comparison still reduces to localized horizontal ordering after context gathering"
        ---

## SOP
1. Confirm this applies: when object names may be broad, unusual, or visually confusable and a quick scene summary can disambiguate them; when the image contains multiple candidate instances and extra context helps identify the intended pair; when a natural-image left/right comparison still reduces to localized horizontal ordering after context gathering
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the two queried objects are already straightforward to localize without scene-level context; when the scene is cluttered enough that caption-style description is unlikely to resolve referents; when the task is not a simple left/right comparison between visible objects), skip the tool path and answer directly; otherwise answer from the final artifact.
