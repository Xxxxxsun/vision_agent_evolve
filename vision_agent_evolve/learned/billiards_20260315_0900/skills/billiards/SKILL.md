---
name: billiards
description: "A multi-stage geometric projection procedure to determine the final pocket of a billiards ball by calculating precise rail reflections."
level: mid
depends_on: ["billiards_full_path_projector", "billiards_reflection_calculator"]
applicability_conditions: "Applies to all billiards tasks requiring trajectory prediction where the initial path projection is insufficient or incomplete."
---

## SOP
1. Confirm this applies: A more precise geometric path calculation tool that accounts for the angle of incidence and reflection on the table rails.
2. Run the existing tool chain in order: `python -m tools billiards_full_path_projector <image_path>`
3. Wait for the Observation, then use the newest artifact as the input to `python -m tools billiards_reflection_calculator <artifact_path>`.
4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
