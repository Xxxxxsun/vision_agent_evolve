<!-- Scene-grounded tool chain for cluttered or ambiguous left/right object comparisons. -->

## Tool branch: ImageDescription -> TextToBbox -> relative_position_marker

Use this branch when:
- object names may have synonyms or need scene/context grounding
- the scene is cluttered and a short description can disambiguate candidates
- direct localization would benefit from first confirming likely object categories present

Do not use this branch when:
- both queried objects are visually obvious and can be localized directly
- speed and compactness matter more than extra grounding
- the question already names uniquely identifiable objects with little ambiguity

Procedure:
1. Run **ImageDescription** to get a brief scene summary and confirm the likely presence/identity of the two queried object categories.
2. Run **TextToBbox** for each referenced object using the grounded object names from step 1.
3. Verify that each bbox corresponds to the intended entity named in the question.
4. Run **relative_position_marker** on the two localized objects to determine which has the smaller/larger horizontal image coordinate.
5. Map the result to the question form: if object X is left of object Y, answer "left" for "Is X on the left or right side of Y?"; otherwise answer "right".

Guardrails:
- Do not hardcode object pairs.
- Do not assume typical side placement from priors.
- Use image-plane horizontal position only; do not infer 3D relations.
- If one object cannot be reliably localized, do not guess; re-check the description and bbox selection.
