---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy generic_zoom_for_small_local_evidence."
level: mid
depends_on: []
applicability_conditions: "Use when the referenced entity is identifiable by name but expected to be very small or visually cluttered, making direct attribute reading unreliable.; Use for direct local attribute questions where color is common but not guaranteed, and magnification may help for other short attributes too.; Use when a simple locate-and-read chain may fail because the candidate box is too coarse."
        ---

## SOP
1. Confirm this applies: Use when the referenced entity is identifiable by name but expected to be very small or visually cluttered, making direct attribute reading unreliable.; Use for direct local attribute questions where color is common but not guaranteed, and magnification may help for other short attributes too.; Use when a simple locate-and-read chain may fail because the candidate box is too coarse.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools localized_region_zoom <artifact_path>` and wait for the Observation.
4. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
5. If the avoid condition applies instead (Avoid when the object is already large and clearly visible without zoom.; Avoid when the question depends on text content, in which case text-specific tools are more appropriate.; Avoid when there is no stable target reference for TextToBbox to anchor on.), skip the tool path and answer directly; otherwise answer from the final artifact.
