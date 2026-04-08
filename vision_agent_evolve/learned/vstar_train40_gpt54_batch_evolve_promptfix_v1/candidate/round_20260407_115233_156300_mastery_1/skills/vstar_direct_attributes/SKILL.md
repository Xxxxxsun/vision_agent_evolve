---
name: vstar_direct_attributes
description: "Mastery SOP for vstar_direct_attributes using strategy locate_then_read_local_color."
level: mid
depends_on: []
applicability_conditions: "Use for direct multiple-choice questions asking for the color or other simple local visual attribute of a specifically referenced person-held item, clothing item, or body-adjacent object.; Use when the target entity can be named in text and likely localized reliably before attribute inspection.; Use when baseline failures come from missing small/local evidence rather than global scene misunderstanding."
        ---

## SOP
1. Confirm this applies: Use for direct multiple-choice questions asking for the color or other simple local visual attribute of a specifically referenced person-held item, clothing item, or body-adjacent object.; Use when the target entity can be named in text and likely localized reliably before attribute inspection.; Use when baseline failures come from missing small/local evidence rather than global scene misunderstanding.
2. Run `python -m tools TextToBbox <image_path>` and wait for the Observation.
3. If the previous artifact is still needed, run `python -m tools RegionAttributeDescription <artifact_path>` and wait for the Observation.
4. If the avoid condition applies instead (Avoid when the referenced target is not clearly identifiable from the question text.; Avoid when the task requires counting, OCR, multi-step comparison, or resolving relations between multiple similar entities.; Avoid when a whole-image glance already makes the attribute unambiguous.), skip the tool path and answer directly; otherwise answer from the final artifact.
