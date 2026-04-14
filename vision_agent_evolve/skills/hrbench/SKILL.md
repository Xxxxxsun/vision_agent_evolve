---
name: hrbench
description: "Router skill for local text, symbol, and visual cue recognition in HRBench"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: ["list_images", "get_image_info", "zoom_image", "crop_image"]
final_answer_policy: option_letter
applicability_conditions: "Use for HRBench multiple-choice questions about local text, signs, symbols, and scene details."
---

# HRBench

## Trigger
- Use for HRBench questions where the answer depends on reading local text or inspecting a small visual cue.

## Procedure
1. Locate the decisive region named or implied by the question.
2. Use `zoom_image` if the target text or object is small.
3. Use `crop_image` when isolating one local region will reduce distractors.
4. Compare the inspected evidence against the answer options.
5. Return the matching option letter.

## Tool Hints
- `zoom_image` is the default first tool for tiny text or signs.
- `crop_image` is appropriate after zoom if the scene is still cluttered.

## Failure Checks
- Avoid answering from a nearby distractor sign or symbol.
- Double-check the final option letter against the inspected region.
