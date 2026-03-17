---
name: mirror_clock
description: "Standard operating procedure for reading time from mirrored analog clock images."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: Apply a horizontal flip (mirror) transformation to the image to normalize the clock face.
2. Run `python -m tools mirror_flip <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The original image shows a clock with mirrored numbers and hands. No tool-generated artifact was produced. The agent skipped the necessary image processing step to reverse the mirror effect, making it impossible to accurately read the time.
