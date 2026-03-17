---
name: billiards
description: "Standard operating procedure for predicting the final pocket of a billiards ball by simulating its trajectory."
level: mid
depends_on: []
applicability_conditions: "Applies to all tasks involving a billiards table, a ball, and a directional indicator (arrow) where the final pocket must be determined."
---

## SOP
1. Confirm this applies: A tool to calculate and draw the reflection path of the ball based on the arrow vector.
2. Run `python -m tools billiards_simulator <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The image shows a blue ball on a billiards table with a green arrow indicating direction. The agent failed to perform the geometric trajectory calculation. The task requires precise geometric path tracing which VLMs struggle with visually; a tool to compute the reflection path is necessary.
