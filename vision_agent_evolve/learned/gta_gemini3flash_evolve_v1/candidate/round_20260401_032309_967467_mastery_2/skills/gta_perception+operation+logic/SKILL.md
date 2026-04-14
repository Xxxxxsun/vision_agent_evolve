---
name: gta_perception+operation+logic
description: "Mastery SOP for gta_perception+operation+logic using strategy visual_evidence_search."
level: mid
depends_on: []
applicability_conditions: "The food item in the image is small or requires identification before searching for its properties.; The user provides a specific year or source (e.g., USDA 2021) that must be verified externally."
        ---

## SOP
1. Confirm this applies: The food item in the image is small or requires identification before searching for its properties.; The user provides a specific year or source (e.g., USDA 2021) that must be verified externally.
2. Run `python -m tools localized_region_zoom <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (The image contains clear, large text that does not require magnification.; The question can be answered using general knowledge without external verification.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
