---
name: billiards
description: "Standard operating procedure for solving billiards trajectory tasks with a deterministic reflection solver."
level: mid
depends_on: []
applicability_conditions: "Applies when the image shows a blue billiards ball, a muted green direction arrow, and a rectangular table with six numbered pockets."
---

## SOP
1. Confirm this applies: the task asks which numbered pocket the blue ball will enter, and the image includes a muted green direction arrow and a rectangular inner rail.
2. Run `python -m tools billiards_reflection_solver <image_path>`.
3. Wait for the Observation, then inspect the reported pocket number and the trajectory artifact before giving any final answer.
4. Answer with the single pocket digit from the solver output. If still failing, verify the detected ball center, arrow tip direction, and the first dark inner rail boundary used for reflections.
