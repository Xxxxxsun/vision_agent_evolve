<!-- Localization-first branch for visible color questions on named objects or clothing/accessories. -->

## Tool branch: localized_color_focus

Use this branch when:
- The question asks for the **color** of a **named object, accessory, or clothing item** visible in the image.
- The target is likely **small**, **attached to a person**, partially occluded, or otherwise easy to misjudge from the full image.
- Success depends on **isolating the referenced region before judging color**.

Do not use this branch when:
- The question depends on **reading text, numbers, or labels**.
- The asked attribute is **not a visible local attribute**.
- The target is **extremely obvious, large, and distinctive**, so localization adds little value.

Procedure:
1. Run `python -m tools localized_color_focus <image_path>` to create an overview plus labeled crop panel.
2. Inspect the tool artifact first; match the named target object to the most relevant labeled crop or overview region.
3. Judge the target object's visible color from that crop/region and map it to the provided answer choices.
4. If the crop panel does not contain the target clearly, fall back to the original image and state the best grounded option.

Notes:
- Do not hardcode object categories, sides, or coordinates.
- Do not assume the answer colors are limited to common examples; inspect the region first.
- The preferred command is exactly: `python -m tools localized_color_focus <image_path>`.
