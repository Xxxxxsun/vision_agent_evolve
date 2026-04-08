---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy scene_scan_then_localize."
level: mid
depends_on: []
applicability_conditions: "when the image contains many objects and the target pair may be hard to identify from names alone; when the object terms could refer to several candidates and a quick scene summary would help disambiguate; when illustrated or unusual scenes make initial object grounding uncertain"
        ---

## SOP
1. Confirm this applies: when the image contains many objects and the target pair may be hard to identify from names alone; when the object terms could refer to several candidates and a quick scene summary would help disambiguate; when illustrated or unusual scenes make initial object grounding uncertain
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the targets are already obvious and extra scene description would add unnecessary steps; when the question is purely about a clearly visible pair with minimal clutter; when the scene description is unlikely to reduce ambiguity), skip the tool path and answer directly; otherwise answer from the final artifact.
