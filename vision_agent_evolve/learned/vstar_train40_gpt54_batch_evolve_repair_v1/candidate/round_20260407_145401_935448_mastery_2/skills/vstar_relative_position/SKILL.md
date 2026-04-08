---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy caption-first-spatial-check."
level: mid
depends_on: []
applicability_conditions: "when object names may have synonyms or the scene context is needed before localization; when the image is cluttered and a brief scene summary can help disambiguate candidate entities; when direct object localization might benefit from confirming the likely object categories present"
        ---

## SOP
1. Confirm this applies: when object names may have synonyms or the scene context is needed before localization; when the image is cluttered and a brief scene summary can help disambiguate candidate entities; when direct object localization might benefit from confirming the likely object categories present
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools relative_position_marker <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (when the two queried objects are visually obvious and can be localized directly; when speed and compactness matter more than extra disambiguation; when the question already names uniquely identifiable objects and no scene grounding is needed), skip the tool path and answer directly; otherwise answer from the final artifact.
