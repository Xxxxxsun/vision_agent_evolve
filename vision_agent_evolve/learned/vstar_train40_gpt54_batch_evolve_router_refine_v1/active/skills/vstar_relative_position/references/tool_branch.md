<!-- Context-assisted localization and horizontal comparison for left/right relation questions. -->

## Tool branch: generic_visual_focus

Use this branch when the task is still a simple left/right comparison, but the referents are not immediately obvious from direct inspection.

### Positive triggers
- Object names are broad, unusual, or visually confusable.
- There may be multiple candidate instances of one or both named objects.
- A quick scene summary is likely to help identify the intended pair.
- After disambiguation, the question still reduces to comparing horizontal position.

### Negative triggers
- The two queried objects are already straightforward to localize without extra context.
- The scene is so cluttered that caption-style description is unlikely to resolve the referents.
- The question requires anything beyond simple left/right comparison of visible objects.
- The answer would require 3D/viewpoint inference or resolving severe occlusion.

### Procedure
1. Run `python -m tools generic_visual_focus <image_path>` to create an overview with left/right guides and spatial crop panels.
2. Inspect the tool artifact and identify the two referenced objects in the overview or crop panels.
3. Compare their horizontal image-plane positions using the left/right guide, not world priors.
4. Map the horizontal ordering to the requested answer choice.

### Output rule
- Answer strictly from the tool-derived horizontal comparison of the intended object pair.
- If disambiguation fails or the objects cannot be localized reliably, do not guess from this branch; fall back only if a direct no-tool comparison is genuinely clear.
