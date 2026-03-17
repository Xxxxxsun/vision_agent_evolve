---
name: gear_rotation
description: "A systematic propagation method to determine the final gear's orientation by tracking rotation direction through mechanical linkages."
level: mid
depends_on: []
applicability_conditions: "Applies to all gear train problems involving multiple gears, meshed connections, and belt-driven linkages."
---

## SOP
1. **Analyze Initial State**: Identify the input gear and determine its initial rotation direction (Clockwise/CW or Counter-Clockwise/CCW) based on the provided arrow.
2. **Map the Sequence**: Identify all gears and their connection types (meshed or belt-driven) in the sequence from the input gear to the final gear.
3. **Apply Propagation Rules**:
   - **Meshed Gears**: Adjacent gears always rotate in opposite directions.
   - **Belt-Connected Gears**: 
     - Uncrossed belts: Connected gears rotate in the same direction.
     - Crossed belts: Connected gears rotate in opposite directions.
4. **Trace Rotation**: Systematically label each gear in the chain with its rotation direction (CW or CCW) until the final gear is reached.
5. **Determine Final Position**: Based on the final gear's calculated rotation direction, determine which numerical position the arrow will point to and provide the final number as the answer.
