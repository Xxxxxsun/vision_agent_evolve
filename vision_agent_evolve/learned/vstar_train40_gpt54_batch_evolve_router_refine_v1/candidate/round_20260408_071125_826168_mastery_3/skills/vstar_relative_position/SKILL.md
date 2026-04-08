---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy single-tool-spatial-marker."
level: mid
depends_on: []
applicability_conditions: "when both referenced objects are large, salient, and easy to visually distinguish; when the family question only asks for left versus right and no fine-grained attribute extraction is needed; when a lightweight spatial support tool is sufficient without explicit object localization"
        ---

## SOP
1. Confirm this applies: when both referenced objects are large, salient, and easy to visually distinguish; when the family question only asks for left versus right and no fine-grained attribute extraction is needed; when a lightweight spatial support tool is sufficient without explicit object localization
2. Run `python -m tools relative_position_marker <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (when the objects are small, numerous, or difficult to tell apart; when precise grounding of named objects is needed before comparing positions; when the image has strong clutter or overlapping objects), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
