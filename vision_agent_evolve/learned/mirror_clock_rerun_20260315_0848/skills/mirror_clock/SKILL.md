---
name: mirror_clock
description: "SOP for reading mirrored and potentially rotated analog clocks by applying sequential image transformations."
level: mid
depends_on: ["mirror_flip", "rotate_clock"]
applicability_conditions: "Applies to all tasks involving mirrored analog clocks, including those where the clock face appears inverted or upside down after a horizontal flip."
---

## SOP
1. Confirm this applies: The clock is not just mirrored, it is rotated. The tool only performed a horizontal flip. The numbers are still upside down/rotated.
2. Run the existing tool chain in order: `python -m tools mirror_flip <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools rotate_clock <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
