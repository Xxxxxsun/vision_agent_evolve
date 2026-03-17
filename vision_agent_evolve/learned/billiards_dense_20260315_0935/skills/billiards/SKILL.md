---
name: billiards
description: "A multi-step geometric path-tracing procedure to determine the final pocket of a billiards ball by simulating full-trajectory rail reflections."
level: mid
depends_on: ["billiards_path_tracer", "billiards_trajectory_solver"]
applicability_conditions: "Applies to all billiards tasks where a ball's trajectory requires calculating multiple rail reflections to identify the destination pocket."
---

## SOP
1. Confirm this applies: A more robust path-tracing algorithm that accounts for multiple rail reflections until a pocket is reached.
2. Run the existing tool chain in order: `python -m tools billiards_path_tracer <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools billiards_trajectory_solver <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, The original image shows a blue ball with a green directional arrow. The tool-generated artifact displays a single green line segment that does not accurately represent the full reflection path of the ball, failing to show the bounce off the rails. The existing tool is insufficient because it produces an incomplete and geometrically incorrect path. A new, more accurate path-tracing tool is required to solve the problem.
