---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy zoom_after_localization."
level: mid
depends_on: []
applicability_conditions: "when the referenced objects are small, far away, or visually subtle; when approximate localization is possible but precise above/below or left/right comparison needs closer inspection; when dense scenes make exact relative placement difficult at full-image scale"
        ---

## SOP
1. Confirm this applies: when the referenced objects are small, far away, or visually subtle; when approximate localization is possible but precise above/below or left/right comparison needs closer inspection; when dense scenes make exact relative placement difficult at full-image scale
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the objects are large and spatially separated enough to compare directly; when localization itself is too unreliable for zooming to help; when the question can be answered from coarse global layout alone), skip the tool path and answer directly; otherwise answer from the final artifact.
