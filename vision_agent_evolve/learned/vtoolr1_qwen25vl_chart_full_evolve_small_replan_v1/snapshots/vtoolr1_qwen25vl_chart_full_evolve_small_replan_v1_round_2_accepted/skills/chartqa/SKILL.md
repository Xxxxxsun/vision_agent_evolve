---
name: chartqa
description: "SOP for extracting and computing differences between chart values (e.g., largest vs. smallest bar)."
level: mid
depends_on: []
applicability_conditions: "Questions asking for differences between chart elements (e.g., bars, lines) where numerical values are overlaid or extractable via OCR."
        ---

## SOP
1. Confirm this applies: Use the validated tool output to answer this task family.
2. Run `python -m tools chart_value_overlay <image_path>`.
3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.
4. Answer the original question using the tool output instead of the raw image. If still failing, Use the validated tool output to answer this task family.
