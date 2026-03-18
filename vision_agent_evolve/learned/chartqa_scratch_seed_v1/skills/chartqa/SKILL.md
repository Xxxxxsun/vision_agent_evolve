---
name: chartqa
description: "Task-conditioned visual editing SOP for ChartQA. Write temporary Python code to remove distractors, preserve target evidence, and answer from the edited image."
level: high
depends_on: []
applicability_conditions: "Use for chart and plot questions where the raw image contains multiple years, categories, legend series, or stacked segments and direct reading is unreliable."
---

## Goal
Do not solve these questions from the raw chart alone when the target evidence is crowded or ambiguous.
For this task family, the default recovery path is to write temporary Python code that edits the current image for the current question, then answer from the edited image.

## Required workflow
1. Read the question and extract the target evidence before writing code.
   - Target year(s)
   - Target category or x-axis label
   - Target legend series / color
   - Whether the question asks for a value, a year, a comparison, or a max/min choice
2. Decide an edit plan in words.
   - What must stay visible
   - What should be masked, dimmed, cropped away, or de-emphasized
   - What should be highlighted or enlarged
3. Use `bash` to write and run temporary Python code.
   - The code must operate on `<image_path>` or the latest image artifact.
   - Save the edited image into the current work directory under `artifacts/` or the current case work folder.
   - Do not print the final answer from the script.
4. After the script runs, inspect the edited image artifact before answering.
5. Answer only after the edited image clearly exposes the target evidence.
6. If the first edit is still noisy, do a second tighter edit on the latest artifact instead of reverting to raw-image guessing.

## Preferred edit patterns
- Single year query:
  Mask or wash out non-target years, keep the target year label and its aligned bar/point/segment visible.
- Single legend / series query:
  Keep the target color strong, dim the other series, and preserve the legend if it is needed to interpret colors.
- Stacked bar query:
  Preserve the target bar and highlight only the requested stacked segment; dim the other segments.
- Dense labels:
  Crop around the relevant axis region plus the target mark, then enlarge the crop.
- Comparison query:
  Keep only the two compared entities and suppress the rest.

## Bad edits to avoid
- Do not only resize or sharpen the full image.
- Do not run OCR on the whole chart before narrowing the target.
- Do not hardcode the answer or dataset-specific coordinates.
- Do not create a permanent learned tool for this mode.

## Temporary code pattern
Use a short Python script with `PIL` or `cv2`. The script should:
1. Load the input image.
2. Apply one or more task-conditioned edits:
   - draw semi-transparent masks over distractors
   - crop to the relevant region
   - enlarge the crop
   - draw a box / outline / translucent highlight on the target evidence
3. Save the edited image to a new file.
4. Print a short status message and the output path.

## Command pattern
Use a bash step that writes a temporary script and runs it immediately. For example:

```bash
cat > "$PWD/chartqa_edit.py" <<'PY'
from PIL import Image, ImageDraw
import sys

src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src).convert("RGBA")
draw = ImageDraw.Draw(img, "RGBA")

# Replace this with a task-conditioned edit plan:
# - mask distractor regions
# - preserve the target label/mark/legend
# - highlight the target evidence

img.save(dst)
print(f"edited image saved to {dst}")
PY
python "$PWD/chartqa_edit.py" "<input_image>" "$PWD/edited_chartqa.png"
```

## Answering rule
When the artifact is available, answer from the edited image, not from memory of the raw image.
If the edited image still does not isolate the requested evidence, run another edit step instead of guessing.
