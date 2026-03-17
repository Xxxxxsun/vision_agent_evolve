---
name: mirror_clock
description: "Standardized procedure for correcting mirrored and rotated analog clock images before time calculation."
level: mid
depends_on: []
applicability_conditions: "Applies to all mirror_clock tasks where the clock face is horizontally reflected and/or vertically inverted."
---

## SOP
1. Confirm this applies: Use the validated tool output to answer this task family.
2. Run the existing tool chain in order: `python -m tools mirror_flip <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools rotate_180 <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, The original image is a mirrored and rotated clock. The artifact is a horizontally flipped version, but it remains upside down. The current tool only handles horizontal reflection. Since the clock is also upside down, a rotation tool is necessary to make the numbers readable for the VLM.
