---
name: rolling_dice_top
description: "Systematic tracking of dice orientation across a grid path using visual annotation and step-by-step state logging."
level: mid
depends_on: []
applicability_conditions: "Applies to all tasks where a standard die is rolled along a defined grid path in a 3D perspective image."
---

## SOP
1. Confirm this applies: A systematic step-by-step tracking tool that maps the die's orientation (top, front, right faces) after each grid movement.
2. Run `python -m tools dice_grid_annotator <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, The image shows a die on a grid with a path indicated by a black arrow. The die starts at a specific grid position and follows the path. The task is a spatial reasoning problem where the agent consistently fails to maintain the state of the die. A tool to formalize the state transition will eliminate the VLM's reliance on visual estimation.
