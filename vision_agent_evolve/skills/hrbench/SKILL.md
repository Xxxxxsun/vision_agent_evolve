---
name: hrbench
description: "SOP for local text, symbol, and visual cue recognition in high-resolution images"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image"]
final_answer_policy: option_letter
applicability_conditions: "Use for HRBench multiple-choice questions about local text, signs, symbols, numbers, or scene details in high-resolution images."
---

# HRBench

## Trigger
- The question asks about a specific piece of text, number, sign, symbol, or local visual detail.
- The image is high-resolution, so the relevant detail is rarely readable at the original scale.

## Procedure
1. Read the question and identify the specific target element (text, number, sign, symbol, or visual cue).
2. Estimate where the target is located in the image using normalized coordinates (0.0 = left/top, 1.0 = right/bottom).
3. Call `zoom_image` with:
   - `center_x` and `center_y` set to the estimated target location — never leave them at 0.5 if the target is off-center.
   - `factor=3` as a starting point; use factor=4–5 for very small or distant targets.
4. Inspect the zoomed result:
   - If the target is now clearly readable, compare it against the answer options.
   - If the target region is still cluttered, use `crop_image` to isolate just the target area with pixel coordinates.
5. Match the inspected evidence to the correct option letter and return it.

## Two-Pass Zoom Strategy
Use this when the target's exact location is uncertain:
1. First zoom: factor=2, center_x=0.5, center_y=0.5 — overview scan to locate the target region.
2. From the overview, estimate the target's center_x/center_y more accurately.
3. Second zoom: factor=4, centered precisely on the target.

## Tool Hints
- `zoom_image` is mandatory for HRBench — never attempt to read small text directly from the original image.
- For text in the upper-left area: center_x≈0.2, center_y≈0.2.
- For text in the lower-right area: center_x≈0.8, center_y≈0.8.
- `crop_image` after zoom: call `get_image_info` on the zoomed image first to get its dimensions, then crop.
- Use `crop_image` when surrounding distractors make it hard to identify the exact target after zooming.

## Failure Checks
- Do not attempt to answer from the original image — the resolution is too high for direct reading.
- Do not zoom to (0.5, 0.5) if the target is clearly in a corner or edge region.
- Do not read a nearby but incorrect sign, label, or number — confirm the identity before answering.
- After reading the target value, double-check it against the available options before committing.

See branch detail:
- `references/localization.md`
