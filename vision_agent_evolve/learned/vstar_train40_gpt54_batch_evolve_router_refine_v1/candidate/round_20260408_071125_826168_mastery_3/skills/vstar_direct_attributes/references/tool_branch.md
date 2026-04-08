<!-- Localization-first branch for visible color questions on named objects or clothing/accessories. -->

## Tool branch: TextToBbox -> RegionAttributeDescription

Use this branch when:
- The question asks for the **color** of a **named object, accessory, or clothing item** visible in the image.
- The target is likely **small**, **attached to a person**, partially occluded, or otherwise easy to misjudge from the full image.
- Success depends on **isolating the referenced region before judging color**.

Do not use this branch when:
- The question depends on **reading text, numbers, or labels**.
- The asked attribute is **not a visible local attribute**.
- The target is **extremely obvious, large, and distinctive**, so localization adds little value.

Procedure:
1. Use **TextToBbox** with the noun phrase naming the target item from the question.
2. Use **RegionAttributeDescription** on the returned region to inspect the item's visible attributes, focusing on **color**.
3. Map the observed color to the provided answer choices.
4. If localization is uncertain, avoid guessing from the whole image; rely on the best grounded region result.

Notes:
- Do not hardcode object categories, sides, or coordinates.
- Do not assume the answer colors are limited to common examples; inspect the region first.
- The preferred chain is exactly: **TextToBbox -> RegionAttributeDescription**.
