---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy zoom-after-localization."
level: mid
depends_on: []
applicability_conditions: "when the referenced objects are small, distant, or easy to miss in the full image; when there are multiple similar objects and closer inspection of candidate regions is helpful; when coarse localization is possible but precise left/right comparison needs better visual support"
        ---

## SOP
1. Confirm this applies: when the referenced objects are small, distant, or easy to miss in the full image; when there are multiple similar objects and closer inspection of candidate regions is helpful; when coarse localization is possible but precise left/right comparison needs better visual support
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when both objects are large and clearly separated in the original image; when localization itself is unreliable and zooming candidate regions would amplify ambiguity; when the task is not a simple image-plane left/right relation), skip the tool path and answer directly; otherwise answer from the final artifact.
