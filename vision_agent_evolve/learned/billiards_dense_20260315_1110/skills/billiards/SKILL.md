---
name: billiards
description: "Standard operating procedure for calculating billiards trajectories using a two-stage geometric extraction and solver pipeline."
level: mid
depends_on: []
applicability_conditions: "Applies to all billiards tasks requiring pocket identification based on ball position and trajectory vectors, particularly when initial trajectory estimation is inaccurate."
---

## SOP
1. Confirm this applies: A more robust geometric extraction tool that precisely calculates the reflection points based on the ball center and arrow vector.
2. Run the existing tool chain in order: `python -m tools billiards_trajectory_precise <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools billiards_geometry_solver <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, The original image shows a blue ball with a green arrow pointing towards the top-right rail. The tool-generated artifacts show inconsistent ball positions and incorrect, incomplete, or misaligned trajectory lines. The current tool is producing hallucinated or misaligned trajectories. A more precise geometric calculation tool is required to solve the reflection physics correctly.
