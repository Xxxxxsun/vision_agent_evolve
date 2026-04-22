# VTool-R1 RL Result Snapshot 2026-04-22

This note records the current `VTool-R1`-related benchmark snapshots we ran in this repo, together with the artifact paths needed to reopen the exact runs.

## Scope

- `table`: protocol-aligned `VTool-R1 focus_on_*` tool flow
- `chart`: structured benchmark `forced_skill_fc` line used for the earlier `75.06%` 7B run
- judge model: `gpt-4o-2024-08-06` where available

## Table: protocol-aligned VTool-R1 tool line

Common setup for the base-model runs below:

- tools: `focus_on_columns_with_mask`, `focus_on_rows_with_mask`, `focus_on_columns_with_draw`, `focus_on_rows_with_draw`
- protocol: `rl_trained_table`
- second rollout: `fresh_crop_primary_answer`
- executor shim: `execshim_v2`

### Reference RL run

| Model | Exact | Judge | Artifacts |
| --- | ---: | ---: | --- |
| `VTool-Qwen2.5-7B` RL | `194/304 = 63.82%` | `207/304 = 68.09%` | [exact](../artifacts/vtool_protocol_eval/table_rl_7b_protocol_aligned_full/summary.json), [judge](../artifacts/vtool_protocol_eval/table_rl_7b_protocol_aligned_full/gpt4o_judge/summary.json) |

### Same-tool base-model runs

| Model | Exact | Judge | Artifacts |
| --- | ---: | ---: | --- |
| `Qwen2.5-VL-7B-Instruct` | `168/304 = 55.26%` | `205/304 = 67.43%` | [exact](../artifacts/vtool_protocol_eval/table_base_7b_protocol_aligned_full_20260421_crop_primary_execshim_v2_rerun1/summary.json), [judge](../artifacts/vtool_protocol_eval/table_base_7b_protocol_aligned_full_20260421_crop_primary_execshim_v2_rerun1/gpt4o_20240806_judge/summary.json) |
| `Qwen2.5-VL-3B-Instruct` | `51/304 = 16.78%` | `158/304 = 51.97%` | [exact](../artifacts/vtool_protocol_eval/table_base_3b_protocol_aligned_full_20260422_crop_primary_execshim_v1/summary.json), [judge](../artifacts/vtool_protocol_eval/table_base_3b_protocol_aligned_full_20260422_crop_primary_execshim_v1/gpt4o_20240806_judge/summary.json) |
| `Qwen2.5-VL-32B-Instruct` | `215/304 = 70.72%` | `254/304 = 83.55%` | [exact](../artifacts/vtool_protocol_eval/table_base_32b_protocol_aligned_full_20260422_crop_primary_execshim_v1/summary.json), [judge](../artifacts/vtool_protocol_eval/table_base_32b_protocol_aligned_full_20260422_crop_primary_execshim_v1/gpt4o_20240806_judge/summary.json) |

### Table takeaways

- The current best same-tool base-model result is `Qwen2.5-VL-32B-Instruct` at `70.72%` exact and `83.55%` GPT-4o judge.
- The current best 7B same-tool base-model result is `55.26%` exact and `67.43%` judge.
- The RL-trained `VTool-Qwen2.5-7B` still beats the 7B base model on exact, but the gap is small on judge: `68.09%` vs `67.43%`.

## Chart: structured `forced_skill_fc` line

Common setup for the runs below:

- dataset: `refocus_chart`
- setting: `frozen_inference_fc_forced_skill`
- forced skill: `refocus_chart_h_bar`
- capability root: `learned/vtoolr1_refocus_chart_manual_v4/active`
- held-out split: full `test` set (`826`)

| Model | Exact | Judge | Artifacts |
| --- | ---: | ---: | --- |
| `Qwen2.5-VL-7B-Instruct` | `620/826 = 75.06%` | not run in this snapshot | [exact](../artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual_v4_full/summary.json) |
| `Qwen2.5-VL-3B-Instruct` | `492/826 = 59.56%` | not run in this snapshot | [exact](../artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual_v4_full_3B_forcedskill_fc_20260422/summary.json) |
| `Qwen2.5-VL-32B-Instruct` | `669/826 = 80.99%` | `691/826 = 83.66%` | [exact](../artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual_v4_full_32B_forcedskill_fc_20260422/summary.json), [judge](../artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual_v4_full_32B_forcedskill_fc_20260422/gpt4o_20240806_judge/summary.json) |

### Chart takeaways

- On this line, `Qwen2.5-VL-32B-Instruct` is the current best result at `80.99%` exact and `83.66%` GPT-4o judge.
- Relative to the 7B baseline, 32B improves chart exact by `+5.93` points.
- Relative to the 3B run, 32B improves chart exact by `+21.43` points.

## Extra artifact paths

- Table RL per-case: [per_case.jsonl](../artifacts/vtool_protocol_eval/table_rl_7b_protocol_aligned_full/per_case.jsonl)
- Table 7B per-case: [per_case.jsonl](../artifacts/vtool_protocol_eval/table_base_7b_protocol_aligned_full_20260421_crop_primary_execshim_v2_rerun1/per_case.jsonl)
- Table 32B per-case: [per_case.jsonl](../artifacts/vtool_protocol_eval/table_base_32b_protocol_aligned_full_20260422_crop_primary_execshim_v1/per_case.jsonl)
- Chart 32B judge input conversion: [judge_input.jsonl](../artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual_v4_full_32B_forcedskill_fc_20260422/judge_input.jsonl)
- Chart 32B judge per-case: [judge_per_case.jsonl](../artifacts/structured_benchmarks/vtoolr1_refocus_chart_manual_v4_full_32B_forcedskill_fc_20260422/gpt4o_20240806_judge/judge_per_case.jsonl)
