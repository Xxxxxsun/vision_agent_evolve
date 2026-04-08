---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy localized_color_inspection."
level: mid
depends_on: []
applicability_conditions: "Use when the question explicitly asks for the color of a named object, clothing item, or accessory.; Use when the likely evidence is localized and color is the only needed attribute.; Use when a lightweight visual focus tool is sufficient without needing full bbox extraction."
        ---

## SOP
1. Confirm this applies: Use when the question explicitly asks for the color of a named object, clothing item, or accessory.; Use when the likely evidence is localized and color is the only needed attribute.; Use when a lightweight visual focus tool is sufficient without needing full bbox extraction.
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (Do not use when the question asks for non-color attributes that need broader context.; Do not use when the task depends on text, counting, or multi-step reasoning.; Do not use when the scene contains many similar candidate objects and exact referent localization is necessary.), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
