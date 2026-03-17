---
name: mirror_clock
description: "Standard operating procedure for correcting and reading mirror-reflected clock faces."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: Apply a horizontal flip to the image to normalize it, then read the clock hands and perform the time arithmetic.
2. Run `python -m tools mirror_flip datasets/mira/images/2.png`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Instruct the agent to: 1) Flip the image horizontally, 2) Read the time from the flipped clock, 3) Add 8 hours and 10 minutes to that time. If still failing, The agent cannot mentally invert the mirror image reliably; a visual transformation tool is necessary to ground the reading, followed by a clear procedural skill.
