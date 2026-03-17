---
name: cubes_missing
description: "A systematic grid-based decomposition process to accurately count missing cubes by mapping the structure to a 2D height map."
level: mid
depends_on: []
applicability_conditions: "Applies to all tasks involving 3D cube structures where occlusion or non-uniform heights make manual counting prone to error."
---

## SOP
1. Confirm this applies: A grid-based decomposition tool that labels each column's height to facilitate explicit summation.
2. Run `python -m tools grid_overlay_tool <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The image shows an isometric view of a stepped structure made of cubes. The structure is 4x3 in base footprint with varying heights. The agent is failing at spatial reasoning/counting. Providing a grid overlay tool will force the agent to decompose the problem into manageable local counts rather than estimating the whole.
