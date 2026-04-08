<!-- Localization-first branch for direct attribute questions when the target entity is not reliably judged from the full image. -->

## Tool Branch: TextToBbox -> RegionAttributeDescription

### Use this branch when
- The question asks for a directly visible attribute of a specifically named object, accessory, garment, or person.
- The referent may be small, partially occluded, surrounded by distractors, or otherwise hard to isolate from the full image.
- Multiple-choice options are visually confusable, and local inspection would reduce uncertainty.

### Do not use this branch when
- The target is already obvious at full-image scale and its attribute is unambiguous.
- The question requires counting, reading text, comparing multiple similar entities, or inference beyond direct appearance.
- The referent cannot be described well enough for localization.

### Procedure
1. Read the question and extract the exact referent and requested attribute.
2. Run `TextToBbox` with the named referent to localize the target region.
3. Run `RegionAttributeDescription` on the returned box, requesting the asked attribute.
4. Verify the region corresponds to the intended referent rather than a nearby distractor.
5. Map the observed attribute to the answer choices and return the matching option.

### Success checks
- The localized box clearly matches the named entity.
- The attribute result is derived from the localized region, not from scene-level guessing.
- The final answer is one of the provided choices and directly supported by the local evidence.
