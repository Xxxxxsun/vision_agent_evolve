---
name: mirror_clock
description: "Standard operating procedure for reading and calculating time from mirrored clock images."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: A reliable method to flip the image horizontally and then read the time from the corrected orientation.
2. Run `python -m tools mirror_flip <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The agent struggles with mental spatial transformation of the mirrored clock. Providing a tool to physically correct the image and a clear step-by-step procedure will eliminate the ambiguity in reading the hands.
