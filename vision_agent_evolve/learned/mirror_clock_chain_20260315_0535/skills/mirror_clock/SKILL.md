---
name: mirror_clock
description: "Standard operating procedure for reading mirrored analog clocks by correcting orientation before calculation."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: A horizontal flip transformation to restore the clock face to a standard reading orientation.
2. Run `python -m tools mirror_flip_tool <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The original image shows a mirrored analog clock face with reversed numbers and hands. No tool-generated artifacts exist. The clock is mirrored; the agent cannot accurately read the time without first reversing the image to a standard format.
