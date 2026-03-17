---
name: mirror_clock
description: "Standard operating procedure for reading time from a mirrored analog clock and calculating a future time."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: A functional image-flipping tool and a reasoning step to interpret the mirrored clock face.
2. Run `python -m tools mirror_clock_transformer <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
