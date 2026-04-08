---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_inspect_color."
level: mid
depends_on: []
applicability_conditions: "Use when the question asks for the color of a specifically named object in a natural image; Use when the target object must first be localized before its local color can be inspected; Use when the object may be small, partially occluded, or one of several foreground items"
        ---

## SOP
1. Confirm this applies: Use when the question asks for the color of a specifically named object in a natural image; Use when the target object must first be localized before its local color can be inspected; Use when the object may be small, partially occluded, or one of several foreground items
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the object is already visually obvious and large enough to answer directly; Avoid when the question requires relational reasoning, counting, reading text, or non-color attributes; Avoid when localization is too ambiguous and no candidate box clearly matches the named object), skip the tool path and answer directly; otherwise answer from the final artifact.
