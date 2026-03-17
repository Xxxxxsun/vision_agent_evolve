---
name: billiards
description: "Standard operating procedure for calculating billiard ball trajectories using a two-stage geometric path-tracing and solving process."
level: mid
depends_on: ["billiards_path_tracer", "billiards_geometric_solver"]
applicability_conditions: "Applies to all billiards tasks requiring trajectory prediction based on a ball position and a directional arrow, particularly when initial path tracing is insufficient or requires verification."
---

## SOP
1. Confirm this applies: A more robust path-tracing tool that correctly calculates vector reflection based on the provided green arrow's orientation.
2. Run the existing tool chain in order: `python -m tools billiards_path_tracer <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools billiards_geometric_solver <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, The original image shows a blue ball with a green arrow pointing up-right. The tool-generated artifact shows an incorrect trajectory (a red line pointing down-left) and misplaces the ball. The existing tool is producing incorrect geometric outputs; a more precise path-tracing tool is required to correctly map the trajectory.
