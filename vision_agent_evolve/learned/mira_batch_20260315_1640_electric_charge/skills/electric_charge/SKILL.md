---
name: electric_charge
description: "A systematic procedure for calculating the net electrostatic force on a target charge using vector decomposition."
level: mid
depends_on: []
applicability_conditions: "Applies to all electric charge problems requiring the determination of a net force vector from multiple source charges in a 2D plane."
---

## SOP for Net Electrostatic Force Calculation

1. **Identify Charges**: Identify the target charge and all surrounding source charges from the provided image.
2. **Determine Force Directions**: For each source charge, determine the direction of the force exerted on the target charge (repulsive for like charges, attractive for opposite charges).
3. **Estimate Relative Magnitudes**: Apply Coulomb's Law (F ∝ |q1*q2|/r²) to estimate the relative magnitude of each force vector based on the charge values and their distances from the target.
4. **Vector Decomposition**: 
   - Define a coordinate system.
   - Decompose each individual force vector into its x (F_x) and y (F_y) components using the geometry of the arrangement (trigonometry).
5. **Vector Summation**: 
   - Sum all x-components: ΣF_x = F_1x + F_2x + ...
   - Sum all y-components: ΣF_y = F_1y + F_2y + ...
6. **Determine Resultant**: Use the resultant components (ΣF_x, ΣF_y) to determine the final direction and relative magnitude of the net force vector.
7. **Final Answer**: State the direction of the net force clearly based on the calculated resultant vector.
