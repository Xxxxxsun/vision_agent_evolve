---
name: mirror_clock
description: "Standard operating procedure for interpreting mirrored clock faces and performing time-based calculations."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: A reliable way to flip the image horizontally to restore standard clock orientation before reading the time.
2. Run `python -m tools mirror_flip <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The agent consistently struggles with the mental transformation of mirrored text/hands. Providing a tool to physically flip the image removes the ambiguity, and a skill update ensures the agent follows the logical sequence of correction before calculation.
