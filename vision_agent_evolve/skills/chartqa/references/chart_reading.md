---
name: chartqa_chart_reading
description: "Region estimation guide for reading different chart types in ChartQA"
level: low
---

# Chart Reading — Region Estimation Guide

## Chart Type Patterns

### Bar Chart
- Plot area (bars): center_x ≈ 0.50, center_y ≈ 0.50
- X-axis category labels (below bars): center_y ≈ 0.88–0.95
- Y-axis numeric scale (left edge): center_x ≈ 0.08
- Legend (typically top-right): center_x ≈ 0.80, center_y ≈ 0.10
- For a specific bar among many: estimate center_x proportionally (e.g., 3rd bar of 6 ≈ center_x 0.45)

### Line Chart
- Plot area (lines and data points): center_x ≈ 0.55, center_y ≈ 0.50
- X-axis labels (dates, categories): center_y ≈ 0.88–0.95
- Y-axis scale: center_x ≈ 0.08
- Legend (top or right side): check both center_y≈0.10 and center_x≈0.90

### Pie/Donut Chart
- Chart body: center_x ≈ 0.50, center_y ≈ 0.50
- Slice labels (outside rim): zoom the full chart at factor=2 first, then zoom the specific slice direction
- Legend (usually right or below): center_x ≈ 0.80 or center_y ≈ 0.88

### Stacked/Grouped Bar Chart
- Same as bar chart for the overall region
- For a specific segment within a stacked bar: zoom the bar's x-position and the approximate y-range of that segment

## Two-Pass Zoom Strategy
When the chart is complex or the target element is unclear:
1. First zoom: factor=2, center_x=0.5, center_y=0.5 — get an overview of the full plot
2. Identify the target region from the overview
3. Second zoom: factor=3 or higher, center_x/center_y at the specific element

## Reading Axis Values
- Always read both the axis tick value AND the corresponding bar/line height together.
- If tick marks are crowded, zoom the axis edge (center_x≈0.08 for y-axis) at factor=3.
- For percentage-based axes: confirm the unit at the top or label of the y-axis before extracting.
