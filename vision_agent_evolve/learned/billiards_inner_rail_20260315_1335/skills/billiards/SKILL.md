---
name: billiards
description: "Standard operating procedure for determining the final pocket of a billiard ball using geometric path-tracing."
level: mid
depends_on: []
applicability_conditions: "Applies to all tasks involving a billiards table, a ball, and a directional indicator where the final pocket must be determined through trajectory projection."
---

## SOP
1. Confirm this applies: A geometric path-tracing tool to draw the trajectory line including reflections.
2. Run `python -m tools billiards_path_tracer <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The image shows a billiards table with a blue ball and a green arrow indicating a trajectory towards the bottom-left rail. Visualizing the path is necessary for the agent to accurately determine the final pocket, as mental projection is prone to error.
