---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_evidence_focus_then_localize."
level: mid
depends_on: []
applicability_conditions: "Use for localized object color questions when the scene is cluttered, the target is small, or color evidence may be subtle; Use when a preliminary color-focused view can make subsequent localization and attribute reading more reliable; Use when multiple choice options are all color names and the task is pure visual attribute lookup"
        ---

## SOP
1. Confirm this applies: Use for localized object color questions when the scene is cluttered, the target is small, or color evidence may be subtle; Use when a preliminary color-focused view can make subsequent localization and attribute reading more reliable; Use when multiple choice options are all color names and the task is pure visual attribute lookup
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (Do not use when the target object is already easy to find at normal scale; Do not use when the task depends on text, counts, or non-color attributes; Do not use when the image is too low quality for color highlighting to add value), skip the tool path and answer directly; otherwise answer from the final artifact.
