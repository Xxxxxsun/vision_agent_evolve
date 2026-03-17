---
name: gear_rotation
description: "A systematic procedure for tracking rotation direction across gear trains and belt systems using visual labeling."
level: mid
depends_on: ["gear_tracker"]
applicability_conditions: "Applies to all tasks involving sequences of interconnected gears or belts where the final rotation direction must be determined."
---

## SOP
1. Confirm this applies: A systematic tracking tool to label the rotation direction (CW/CCW) of each gear in the sequence.
2. Run `python -m tools gear_tracker <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
