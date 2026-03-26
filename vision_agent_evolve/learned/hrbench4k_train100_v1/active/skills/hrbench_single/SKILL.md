---
name: hrbench_single
description: "For HRBench single-image questions, inspect a labeled focus grid before answering so local text, logos, colors, directions, and small objects are easier to verify."
level: mid
depends_on: ["hrbench_focus_grid_tool"]
applicability_conditions: "Use this SOP for hrbench_single questions that depend on evidence from one local region, such as text, logos, colors, directions, small objects, or a person/object attribute."
---

## SOP
1. Confirm this applies: the question asks about a single image and likely depends on one local cue rather than multi-image comparison.
2. Run `python -m tools hrbench_focus_grid_tool <image_path>`.
3. Wait for the Observation and inspect the labeled panels in the artifact:
   original, center crop, top left, top right, bottom left, bottom right, center sharpened.
4. Pick the panel that makes the target evidence easiest to see. Use that panel, not a vague impression from the raw image.
5. If the question asks about text, logos, numbers, or brand names, answer with the shortest exact string you can read.
6. If the question asks about color, direction, side, or location, answer with the shortest precise phrase or option letter.
7. Only use `python -m tools color_recognition_tool <image_path>` as an extra fallback when the question is specifically about backpack color near a person wearing a yellow shirt.
8. Do not add explanation unless the benchmark explicitly requires it; prefer the shortest correct final answer or option letter.
