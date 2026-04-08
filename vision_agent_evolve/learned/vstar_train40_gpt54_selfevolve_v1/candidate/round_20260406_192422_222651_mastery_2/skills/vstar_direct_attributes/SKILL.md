---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy localized_color_focus_first."
level: mid
depends_on: []
applicability_conditions: "when the task asks for a local visible color attribute with multiple-choice options; when the target region is likely small, partially occluded, or visually easy to miss; when failures tend to come from not directing attention to the right local evidence"
        ---

## SOP
1. Confirm this applies: when the task asks for a local visible color attribute with multiple-choice options; when the target region is likely small, partially occluded, or visually easy to miss; when failures tend to come from not directing attention to the right local evidence
2. Run `python -m tools localized_color_focus <image_path>` and wait for the Observation.
3. If the avoid condition applies instead (when the answer depends on text, counts, or relationships between several entities; when the queried attribute is global and clearly visible without tool assistance; when the object identity itself is ambiguous and needs explicit localization first), skip the tool path and answer directly.
4. Answer the original question from the tool output artifact when the tool path is used.
