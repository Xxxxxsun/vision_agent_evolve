---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color-focus-assisted inspection."
level: mid
depends_on: []
applicability_conditions: "when the task is a direct local color-attribute question; when the target object is visible but small, partially occluded, or surrounded by distracting regions; when emphasizing discriminative color evidence is likely to improve attribute reading"
        ---

## SOP
1. Confirm this applies: when the task is a direct local color-attribute question; when the target object is visible but small, partially occluded, or surrounded by distracting regions; when emphasizing discriminative color evidence is likely to improve attribute reading
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (when the target object itself is not yet identified and needs explicit localization from language first; when the question is about text, counts, or spatial relations rather than color; when scene-level color is sufficient and no local focus is needed), skip the tool path and answer directly; otherwise answer from the final artifact.
