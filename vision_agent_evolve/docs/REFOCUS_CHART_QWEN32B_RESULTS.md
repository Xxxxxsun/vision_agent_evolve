# Refocus_Chart Qwen2.5-VL-32B Results

This note records the local same-benchmark evaluation we ran on `VTOOL/Refocus_Chart` using a remote `vLLM` endpoint serving `Qwen2.5-VL-32B-Instruct`.

## Setup

- Dataset: `VTOOL/Refocus_Chart`
- Split evaluated: full `test` split
- Test size: `826`
- Model endpoint: OpenAI-compatible `vLLM`
- Model id exposed by server: `Qwen2.5-VL-32B-Instruct`
- Evaluation date: `2026-04-14 UTC`

## Compared rows

### 1. Direct VLM

- Setting: `direct_vlm`
- Summary: [artifacts/structured_benchmarks/vtoolr1_refocus_chart_direct_test826/summary.json](/root/vision_agent_evolve_rl/vision_agent_evolve/artifacts/structured_benchmarks/vtoolr1_refocus_chart_direct_test826/summary.json)
- Result: `557 / 826`
- Accuracy: `67.43%`

Per-family highlights:

- `h_bar_comparison`: `79.31%`
- `v_bar_comparison`: `80.95%`
- `h_bar_extrema`: `66.67%`
- `v_bar_extrema`: `66.29%`

### 2. Manual Skill + BBox Tools

- Setting: `frozen_inference_forced_skill`
- Capability root: `learned/vtoolr1_refocus_chart_manual/active`
- Summary: [artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual/summary.json](/root/vision_agent_evolve_rl/vision_agent_evolve/artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual/summary.json)
- Result: `410 / 826`
- Accuracy: `49.64%`

This run used:

- built-in bbox tools aligned with the paper tool family:
  - `focus_on_x_values_with_mask`
  - `focus_on_y_values_with_mask`
  - `focus_on_x_values_with_draw`
  - `focus_on_y_values_with_draw`
- one extra handwritten helper:
  - `refocus_chart_region_crop`
- eight handwritten family skills covering:
  - `h_bar / v_bar`
  - `generic / count_or_total / extrema / comparison`

Per-family highlights:

- `h_bar_generic`: `51.57%`
- `v_bar_generic`: `56.45%`
- `h_bar_comparison`: `48.28%`
- `v_bar_comparison`: `33.33%`

## Comparison to VTool-R1 reported row

From the `VTool-R1` paper table on the chart split:

- direct: `76.2`
- prompted tool-use baseline: `53.4`
- `VTool-R1`: `80.7`

Local deltas from our run:

- local `direct_vlm` vs reported `VTool-R1`: `-13.27` points
- local handwritten `skill + tool` vs reported `VTool-R1`: `-31.06` points
- handwritten `skill + tool` vs local `direct_vlm`: `-17.80` points

## Interpretation

The handwritten `skill + tool` line underperformed the plain direct model. The failure pattern is not that tools were unavailable; the run used tools almost every case (`tool_usage_rate = 1.0`). The more likely issue is that the handwritten SOPs and tool orchestration are not yet strong enough to improve over the base model on this benchmark.

This means the current handwritten capability root should be treated as:

- a reproducible manual baseline
- a debugging artifact for tool-policy design
- not yet a competitive same-benchmark replacement for the direct model

## Key files

- Dataset preparation:
  - [scripts/download_refocus_chart.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/download_refocus_chart.py)
  - [scripts/prepare_refocus_chart.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/prepare_refocus_chart.py)
- Manual capability root:
  - [learned/vtoolr1_refocus_chart_manual/active/tools/refocus_chart_region_crop.py](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/tools/refocus_chart_region_crop.py)
  - [learned/vtoolr1_refocus_chart_manual/active/skills](</root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills>)
