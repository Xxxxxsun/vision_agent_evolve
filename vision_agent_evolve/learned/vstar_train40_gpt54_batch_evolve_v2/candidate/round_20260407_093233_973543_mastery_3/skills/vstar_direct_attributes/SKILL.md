---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy zoom_after_localization."
level: mid
depends_on: []
applicability_conditions: "when the named object is likely small or visually cluttered and a simple localization may not be enough; when fine-grained color judgment is needed after identifying the object region; when direct object-color lookup is supported but evidence quality may benefit from magnification"
        ---

## SOP
1. Confirm this applies: when the named object is likely small or visually cluttered and a simple localization may not be enough; when fine-grained color judgment is needed after identifying the object region; when direct object-color lookup is supported but evidence quality may benefit from magnification
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the target object is large and clearly visible without zoom; when the task is not about a single localized object's color; when localization is too uncertain to make zooming useful), skip the tool path and answer directly; otherwise answer from the final artifact.
