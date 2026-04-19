---
name: hrbench_localization
description: "Position estimation and multi-pass zoom guide for HRBench high-resolution images"
level: low
---

# Localization — Position Estimation for HRBench

## Spatial Estimation Guide

Use this as a reference when estimating center_x and center_y for the target element:

| Target location | center_x | center_y |
|----------------|----------|----------|
| Top-left corner | 0.15 | 0.15 |
| Top-center | 0.50 | 0.10 |
| Top-right corner | 0.85 | 0.15 |
| Left edge, middle height | 0.10 | 0.50 |
| Center of image | 0.50 | 0.50 |
| Right edge, middle height | 0.90 | 0.50 |
| Bottom-left corner | 0.15 | 0.85 |
| Bottom-center | 0.50 | 0.90 |
| Bottom-right corner | 0.85 | 0.85 |

## Multi-Pass Zoom Procedure

### When the target location is uncertain:
1. First pass: `zoom_image(image_id, factor=2, center_x=0.5, center_y=0.5)`
   - Gets a 2× overview of the full image
   - Use this to identify roughly where the target sits
2. Translate the observed position to normalized coordinates
3. Second pass: `zoom_image(image_id, factor=4, center_x=<estimated>, center_y=<estimated>)`
   - Targets the specific element with higher magnification

### When multiple similar elements are visible:
- Read the question again carefully to identify which element is being asked about
- Use surrounding context (nearby labels, spatial relationship) to disambiguate
- If still unclear, zoom both candidates and compare against the options

## Crop After Zoom
When `zoom_image` captures the right area but there are still too many distractors:
1. Call `get_image_info` on the zoomed image to get its pixel dimensions (width, height)
2. Estimate the sub-region of the zoomed image that contains just the target
3. Call `crop_image` with approximate pixel bounds (left, top, right, bottom)

Example: if the zoomed image is 800×600 and the target text is in the left half:
```
crop_image(image_id=<zoomed_id>, left=0, top=100, right=400, bottom=500)
```

## Common HRBench Scene Types

- **Document/signage**: text on signs, menus, notices — usually a distinct block; zoom directly to it
- **Street scenes**: license plates, shop names, traffic signs — scattered; use two-pass zoom
- **Indoor scenes**: clocks, price tags, labels — often small and off-center; use factor=4+
- **Symbols/icons**: logos, marks, diagrams — check color and shape after zooming
