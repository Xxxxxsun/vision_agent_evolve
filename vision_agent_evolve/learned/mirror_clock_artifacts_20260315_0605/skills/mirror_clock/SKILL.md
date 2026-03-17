---
name: mirror_clock
description: "Standardized procedure for correcting mirrored and rotated analog clock images before time calculation."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: A rotation correction step is needed after the mirror flip to normalize the clock face.
2. Run the existing tool chain in order: `python -m tools mirror_fixer <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools rotation_fixer <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
