<!-- Grounding branch for ambiguous or uncertain object identity using ImageDescription followed by TextToBbox before deciding the relation. -->

## Tool branch: ImageDescription -> TextToBbox

**Use this branch when:**
- One or both object names are ambiguous, uncommon, visually confusable, or may refer to multiple scene elements.
- A quick scene/object description would help verify what is present before localization.
- Direct localization from the question alone feels unreliable.

**Do not use this branch when:**
- Both objects are obvious and easily localizable without extra grounding.
- The task is outside simple image-plane relative position.

**Procedure**
1. Run `ImageDescription` to get a concise description of the scene and confirm whether the queried object categories appear and how they are referred to visually.
2. Use `TextToBbox` for the first target object.
3. Use `TextToBbox` for the second target object.
4. From the resulting object locations, compare their image-plane positions only:
   - For above/below, compare vertical placement.
   - For left/right, compare horizontal placement.
5. Answer the multiple-choice question from the observed arrangement.

**Decision rule**
- Choose the option that matches the actual image-plane relation between the two grounded objects.
- If grounding reveals the queried objects are absent or unresolved, do not guess from common real-world layouts.

**Guardrails**
- Do not hardcode specific object pairs.
- Do not assume dataset-specific coordinates or fixed compositions.
- Do not use world knowledge in place of visual grounding.
