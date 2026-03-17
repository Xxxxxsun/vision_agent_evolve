---
name: mirror_clock
description: "Standard operating procedure for interpreting and calculating time from mirror-reflected clock images."
level: mid
depends_on: []
---

## SOP
1. Confirm this applies: Apply a horizontal flip to the image to restore standard clock orientation, then read the hands.
2. Run `python -m tools mirror_flip <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The agent skipped the necessary visual transformation and jumped to a conclusion, likely due to a lack of a dedicated mirror-correction tool or explicit instruction to handle mirror-image tasks.
