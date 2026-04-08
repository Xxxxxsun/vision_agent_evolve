---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy scene_scan_then_ground."
level: mid
depends_on: []
applicability_conditions: "Use when the object names are generic but the scene may contain multiple candidate instances and a quick scene summary can reduce ambiguity.; Use when attribute cues such as color or object type may need coarse confirmation before localization.; Use for cluttered natural images where direct left-right answering is risky without first identifying likely target objects."
        ---

## SOP
1. Confirm this applies: Use when the object names are generic but the scene may contain multiple candidate instances and a quick scene summary can reduce ambiguity.; Use when attribute cues such as color or object type may need coarse confirmation before localization.; Use for cluttered natural images where direct left-right answering is risky without first identifying likely target objects.
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (Do not use when the scene is already simple and the two queried objects are obvious at a glance.; Do not use when the image description is unlikely to disambiguate among many identical instances.; Do not use for tasks outside simple relative-position reasoning.), skip the tool path and answer directly; otherwise answer from the final artifact.
