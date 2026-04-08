---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy color_focus_inspection."
level: mid
depends_on: []
applicability_conditions: "Use when the question asks for a directly visible color attribute and the evidence is localized but may be small or visually cluttered; Use when exact object localization from text may be imperfect but highlighting candidate color-evidence regions is sufficient; Use for person-associated items or clothing regions where color is the decisive attribute"
        ---

## SOP
1. Confirm this applies: Use when the question asks for a directly visible color attribute and the evidence is localized but may be small or visually cluttered; Use when exact object localization from text may be imperfect but highlighting candidate color-evidence regions is sufficient; Use for person-associated items or clothing regions where color is the decisive attribute
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the needed evidence is text-like rather than color-based; Avoid when the question requires broader scene reasoning instead of local attribute lookup; Avoid when the object is already clearly visible and answerable without zoomed local inspection), skip the tool path and answer directly; otherwise answer from the final artifact.
