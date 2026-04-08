# VTool-R1 Qwen2.5-VL OpenRouter Experiments

This runbook covers the no-GPU experiment line:

- Base VLM: Qwen2.5-VL through OpenRouter.
- Benchmarks: VTool-R1 Chart Split (`chartqa`) and Table Split (`refocus_tablevqa`).
- We do not run the released VTool-R1 model. VTool-R1 7B is a reported reference.
- The official-tooluse line mirrors the released VTool-R1 "vanilla model, prompt with tool" eval path.
- The same-tool line disables generated tools and uses only VTool-R1 bbox tools.
- The full-evolve line allows this repo's training-free evolution to generate capabilities.

## Environment

As of the current OpenRouter `/api/v1/models` response, `qwen/qwen-2.5-vl-7b-instruct` and
`qwen/qwen2.5-vl-7b-instruct` are not routable model IDs. The available Qwen2.5-VL IDs are:

- `qwen/qwen2.5-vl-32b-instruct`
- `qwen/qwen2.5-vl-72b-instruct`

Use 32B for the no-GPU OpenRouter run:

```bash
export OPENROUTER_API_KEY="..."
export VLM_BASE_URL="https://openrouter.ai/api/v1"
export VLM_MODEL="qwen/qwen2.5-vl-32b-instruct"
```

This is not a same-base 7B comparison against VTool-R1. Treat it as an OpenRouter API reproduction/evolution line. A strict Qwen2.5-VL-7B comparison requires a provider that exposes the 7B VL checkpoint.

`scripts/run_vtoolr1_qwen25vl_experiments.sh` copies `OPENROUTER_API_KEY` into `VLM_API_KEY` when needed and unsets the Alibaba-specific API variables.

## Data

Prepare normalized data:

```bash
python scripts/prepare_vtoolr1_qwen25vl.py \
  --vtool-root /root/VTool-R1 \
  --refocus-root /root/vqa_datasets/datasets/refocus_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_qwen25vl
```

Expected local splits from the current assets:

- `chartqa/train.jsonl`: 14,344 cases
- `chartqa/val.jsonl`: 813 cases
- `chartqa/test.jsonl`: 826 cases
- `refocus_tablevqa/train.jsonl`: 200 deterministic pseudo-train cases
- `refocus_tablevqa/test.jsonl`: 550 deterministic pseudo-test cases

The TableVQA source is `tablevqa_wbb.json`; it does not expose a separate train split locally, so the script creates a deterministic pseudo-split for training-free evolution.

## Runs

Official VTool-R1 Tool Use prompt baseline:

```bash
SCALE=smoke MODE=official_tooluse DATASET=all bash scripts/run_vtoolr1_qwen25vl_experiments.sh
```

This calls `scripts/run_vtoolr1_official_tooluse_baseline.py`, imports prompts from
`/root/VTool-R1/verl/tooluse/prompt_need.py`, imports tools from
`/root/VTool-R1/verl/tooluse/tools.py`, and follows the released eval scripts'
two-rollout flow: first rollout, execute one parsed tool block when present, then
second rollout for the final answer. The runner also uses `temperature=1.0` and
`top_p=0.99`, and `max_tokens=1024`. On OpenRouter, the runner allows bounded
format-repair turns when the model responds with another executable `ACTION` instead of
a final answer, and it feeds Python `print()` output back to the model. Use
`OFFICIAL_WORKERS=8` or higher to increase API-call parallelism.

Smoke same-tool run:

```bash
SCALE=smoke MODE=same_tools DATASET=all bash scripts/run_vtoolr1_qwen25vl_experiments.sh
```

Formal same-tool run:

```bash
SCALE=formal MODE=same_tools DATASET=all bash scripts/run_vtoolr1_qwen25vl_experiments.sh
```

Full-evolve smoke run:

```bash
SCALE=smoke MODE=full_evolve DATASET=all bash scripts/run_vtoolr1_qwen25vl_experiments.sh
```

Full-evolve formal run:

```bash
SCALE=formal MODE=full_evolve DATASET=all bash scripts/run_vtoolr1_qwen25vl_experiments.sh
```

Use `DATASET=chartqa` or `DATASET=tablevqa` to run one dataset only.

## Reference Rows

Reported VTool-R1 7B references are stored in:

- `docs/vtoolr1_reported_chartqa_7b.json`
- `docs/vtoolr1_reported_tablevqa_7b.json`

Reported Qwen2.5-VL-32B Tool Use references are stored in:

- `docs/vtoolr1_reported_chartqa_32b_tooluse.json`
- `docs/vtoolr1_reported_tablevqa_32b_tooluse.json`

Merge one completed same-tool summary with a reference row:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset chartqa \
  --our-summary artifacts/structured_benchmarks/vtoolr1_qwen25vl_chart_formal_v1/summary.json \
  --vtool-result docs/vtoolr1_reported_chartqa_7b.json \
  --our-setting skill_only_frozen_inference \
  --api-label qwen2.5-vl-32b-openrouter \
  --output artifacts/vtool_r1_comparison/chartqa_qwen25vl_openrouter.json
```

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset refocus_tablevqa \
  --our-summary artifacts/structured_benchmarks/vtoolr1_qwen25vl_table_formal_v1/summary.json \
  --vtool-result docs/vtoolr1_reported_tablevqa_7b.json \
  --our-setting skill_only_frozen_inference \
  --api-label qwen2.5-vl-32b-openrouter \
  --output artifacts/vtool_r1_comparison/tablevqa_qwen25vl_openrouter.json
```
