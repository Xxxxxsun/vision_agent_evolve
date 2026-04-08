---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy localize_then_read_color."
level: mid
depends_on: []
applicability_conditions: "Use when the question asks for the color of a named local object, accessory, or clothing item that must be visually isolated first; Use when multiple people or multiple similarly colored regions are present and direct whole-image inspection may confuse the target; Use across direct-attribute multiple-choice cases where the referenced entity can be described in text and then inspected locally"
        ---

## SOP
1. Confirm this applies: Use when the question asks for the color of a named local object, accessory, or clothing item that must be visually isolated first; Use when multiple people or multiple similarly colored regions are present and direct whole-image inspection may confuse the target; Use across direct-attribute multiple-choice cases where the referenced entity can be described in text and then inspected locally
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the target object is already large, unambiguous, and its color is obvious without localization; Avoid when the question is not about a visible local attribute; Avoid when the task depends on reading text, counting, or relational reasoning rather than identifying a dominant local color), skip the tool path and answer directly; otherwise answer from the final artifact.
