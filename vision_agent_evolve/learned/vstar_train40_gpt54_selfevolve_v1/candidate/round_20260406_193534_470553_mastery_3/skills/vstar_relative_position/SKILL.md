---
name: vstar_relative_position
description: "Mastery SOP for vstar_relative_position using strategy caption-to-localize-backoff."
level: mid
depends_on: []
applicability_conditions: "Use when the object names in the question may be ambiguous, uncommon, or easy to confuse, and a quick scene/object description can help verify what is present before localization.; Use when direct localization alone may fail due to uncertainty about object identity."
        ---

## SOP
1. Confirm this applies: Use when the object names in the question may be ambiguous, uncommon, or easy to confuse, and a quick scene/object description can help verify what is present before localization.; Use when direct localization alone may fail due to uncertainty about object identity.
2. Run `python -m tools ImageDescription <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools TextToBbox <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Do not use when the objects are obvious and easily localizable from the question alone.; Avoid for tasks outside simple image-plane relative position, since the added caption step is only a grounding aid.), skip the tool path and answer directly; otherwise answer from the final artifact.
