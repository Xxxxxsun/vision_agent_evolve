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

## Probe Findings

We ran a per-case probe on the `direct_vlm` and handwritten `skill + tool` outputs to locate where the losses actually come from.

Probe artifacts:

- [docs/REFOCUS_CHART_PROBE.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_PROBE.md)
- [docs/reports/refocus_chart_probe_results.json](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/reports/refocus_chart_probe_results.json)
- [scripts/probe_refocus_chart_failures.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/probe_refocus_chart_failures.py)

Main findings:

- `direct_vlm` is mainly losing on:
  - overlong reasoning or truncation: `100`
  - ratio/time/format confusion: `57`
  - truncated output: `21`
- handwritten `skill + tool` is mainly losing on:
  - empty answers: `223`
  - tool-guided wrong answers: `168`

Direct vs handwritten quadrant counts:

- `direct_correct__manual_wrong`: `231`
- `direct_wrong__manual_correct`: `84`
- `direct_correct__manual_correct`: `326`
- `direct_wrong__manual_wrong`: `185`

Interpretation of the probe:

- the current handwritten stack is not failing because bbox metadata or tools are missing
- it is failing because the SOP/tool flow often does not collapse the evidence into a short stable final answer
- the next fix target should be answer-format control and simpler post-tool decision rules, not more tool coverage

## Manual Capability Inventory

The handwritten capability root used in this experiment lives at:

- [learned/vtoolr1_refocus_chart_manual/active](</root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active>)

### Handwritten tool

- [refocus_chart_region_crop.py](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/tools/refocus_chart_region_crop.py)
  Crops the union of selected bbox-labeled regions into a tighter local artifact.
- [refocus_chart_region_crop.json](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/tools/refocus_chart_region_crop.json)
  Manifest describing when the crop helper is intended to be used.

### Handwritten skills

Horizontal-bar families:

- [refocus_chart_chartqa_h_bar_generic](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_h_bar_generic/SKILL.md)
- [refocus_chart_chartqa_h_bar_count_or_total](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_h_bar_count_or_total/SKILL.md)
- [refocus_chart_chartqa_h_bar_extrema](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_h_bar_extrema/SKILL.md)
- [refocus_chart_chartqa_h_bar_comparison](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_h_bar_comparison/SKILL.md)

Vertical-bar families:

- [refocus_chart_chartqa_v_bar_generic](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_v_bar_generic/SKILL.md)
- [refocus_chart_chartqa_v_bar_count_or_total](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_v_bar_count_or_total/SKILL.md)
- [refocus_chart_chartqa_v_bar_extrema](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_v_bar_extrema/SKILL.md)
- [refocus_chart_chartqa_v_bar_comparison](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills/refocus_chart_chartqa_v_bar_comparison/SKILL.md)

### How they are used

These handwritten skills are consumed by the frozen evaluation path with:

- `subset-id = vtoolr1_refocus_chart_manual`
- `--force-skill`

That means the runtime resolves the case family such as:

- `refocus_chart_chartqa_h_bar_generic`
- `refocus_chart_chartqa_v_bar_extrema`

and then loads the matching `SKILL.md` from the capability root above. The built-in bbox tools are still available, and the handwritten crop helper is available as an extra learned tool from the same capability root.

## Key files

- Dataset preparation:
  - [scripts/download_refocus_chart.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/download_refocus_chart.py)
  - [scripts/prepare_refocus_chart.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/prepare_refocus_chart.py)
- Manual capability root:
  - [learned/vtoolr1_refocus_chart_manual/active](</root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active>)
  - [learned/vtoolr1_refocus_chart_manual/active/tools/refocus_chart_region_crop.py](/root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/tools/refocus_chart_region_crop.py)
  - [learned/vtoolr1_refocus_chart_manual/active/skills](</root/vision_agent_evolve_rl/vision_agent_evolve/learned/vtoolr1_refocus_chart_manual/active/skills>)
