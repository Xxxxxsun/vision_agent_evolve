---
name: billiards
description: "Standard operating procedure for determining the target pocket of a billiards ball using geometric path tracing."
level: mid
depends_on: []
applicability_conditions: "Applies to all billiards tasks where a ball trajectory must be determined based on a provided direction arrow and table boundaries."
---

## SOP
1. Confirm this applies: A geometric path-tracing tool that calculates reflections based on the ball's vector and the table boundaries.
2. Run `python -m tools billiards_path_tracer <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The original image shows a billiards table with a blue ball and a green arrow pointing down-left. The agent attempted to trace the path but failed to calculate the correct reflection geometry. Visual estimation of reflection angles is prone to error; a deterministic geometric tool is required to solve the trajectory accurately.
