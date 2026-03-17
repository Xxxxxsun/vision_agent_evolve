---
name: mirror_clock
description: "Standard operating procedure for reading reflected clock faces and calculating future time offsets."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: Horizontal flip of the image to normalize the clock face, followed by time calculation.
2. Run `python -m tools mirror_flip <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
