---
name: mirror_clock
description: "Standard operating procedure for reading a mirror-image clock and performing temporal arithmetic."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: Horizontal reflection of the image followed by reading the time and adding 8 hours and 10 minutes.
2. Run `python -m tools mirror_clock_flipper <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The agent cannot accurately read a mirrored clock face without visual transformation; a flip tool combined with a structured reasoning skill is necessary.
