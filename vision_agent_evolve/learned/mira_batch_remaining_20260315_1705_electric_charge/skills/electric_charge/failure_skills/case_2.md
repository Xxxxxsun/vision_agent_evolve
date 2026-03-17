---
name: electric_charge_case_2_failure_lesson
description: "Guidance for vector-based force analysis in multi-charge systems."
level: low
depends_on: []
applicability_conditions: "Relevant when the task requires determining the net force direction on a single charge influenced by multiple surrounding charges of varying signs."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.
2. Helpful method: The image shows three charges: +Q at the top, -2Q at the bottom left, and +2Q at the bottom right. The agent needs to determine the net force vector on the +Q charge. The agent is struggling with the physics reasoning. A structured step-by-step procedure for vector decomposition and addition will guide the VLM to the correct resultant direction.
3. Common mistake: The agent fails to correctly perform vector addition of the attractive force from -2Q and the repulsive force from +2Q.
4. Next time, consider: Explicitly draw or calculate the force vectors (F1 towards -2Q, F2 away from +2Q) and their resultant.
