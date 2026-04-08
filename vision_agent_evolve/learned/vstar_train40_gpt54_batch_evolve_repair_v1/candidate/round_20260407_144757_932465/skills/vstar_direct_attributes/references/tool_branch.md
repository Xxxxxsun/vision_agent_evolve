<!-- Use localized color inspection for direct color lookup on a named localized region. -->

## Tool branch: localized color for direct attributes

### Use this branch when
- The question asks for the **color** of a named object, accessory, or clothing region.
- The evidence is visually localized and may be small, partially occluded, or in a cluttered scene.
- The target is person-associated (for example, a bag, shirt, hat, shoes) or another specific object whose dominant color determines the answer.
- Exact localization from the text may be imperfect, but inspecting candidate local color regions is sufficient.

### Do not use this branch when
- The needed evidence is **text-like** or requires reading.
- The question asks about **non-color** attributes.
- The task requires **counting**, comparison across many objects, or broader scene/relational reasoning.
- The target color is already obvious enough to answer confidently without additional inspection.

### Procedure
1. Identify the referenced target entity from the question.
2. Run `localized_color_focus` on the image to isolate likely evidence for the target region.
3. Then use `RegionAttributeDescription` on the highlighted/candidate region(s) to verify the dominant visible color.
4. Map the observed dominant color to the provided answer choices.
5. If multiple candidate regions are surfaced, prefer the one that best matches the named target in the question; do not rely on fixed coordinates, largest-person assumptions, or canonical positions.
6. Answer only after grounding the choice in the inspected region output.

### Operational notes
- Treat this as a reusable primitive: **localize first, then identify color**.
- Use tool output over raw-image guessing whenever the target is small, visually ambiguous, or easy to confuse with nearby items.
- Do not hardcode object-specific priors or answer distributions.
