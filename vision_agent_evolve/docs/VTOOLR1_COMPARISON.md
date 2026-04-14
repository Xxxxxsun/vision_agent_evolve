# VTool-R1 API Comparison Workflow

This workflow is for the no-GPU setting:

- use this repo's self-evolution framework
- call a VLM through the existing Alibaba/OpenAI-compatible proxy path
- keep the `VTool-R1` tool protocol fixed
- disable new tool generation
- compare against `VTool-R1` as a reported reference

It is not a same-backbone reproduction of `VTool-R1`. It is a strict same-benchmark, same-tool-pool, training-free API evaluation line.

## Refocus_Chart same-benchmark line

`VTool-R1` reports a unified `Chart Split` result in Table 1 of the ICLR 2026 paper. The open `VTOOL/Refocus_Chart` dataset on Hugging Face is the released chart benchmark variant with:

- `train`: 14,344 rows
- `test`: 826 rows

For the `Qwen2.5-VL-7B` row, the paper reports:

- direct / pure inference: `76.2`
- prompted tool use baseline: `53.4`
- `VTool-R1-7B`: `80.7`

Source: VTool-R1 paper Table 1, chart split (`ICLR 2026`).

## 1. Configure the API client

This repo already supports Alibaba chat and OpenAI-compatible APIs through `core/vlm_client.py`.

Example Alibaba proxy env:

```bash
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_API_KEY="YOUR_PROXY_TOKEN"
export VLM_MODEL="YOUR_VISION_MODEL"
export VLM_USER_ID="YOUR_USER_ID"
export VLM_ACCESS_KEY="YOUR_ACCESS_KEY"
export VLM_QUOTA_ID="YOUR_QUOTA_ID"
```

Only non-secret config is written into `summary.json`:

- `vlm_base_url`
- `vlm_model`
- `vlm_api_style`
- whether Alibaba mode was used

## 2. Prepare datasets

Bootstrap the external assets once:

```bash
bash scripts/bootstrap_vtool_r1_assets.sh
```

Normalize ChartQA:

```bash
python scripts/prepare_chartqa.py \
  --raw-data-root /root/VTool-R1/ChartQA/ChartQA\ Dataset \
  --normalized-data-root ./datasets/structured_vtoolr1_compare
```

Normalize ReFOCUS-TableVQA:

```bash
python scripts/prepare_refocus_tablevqa.py \
  --raw-data-root /root/vqa_datasets/datasets/refocus_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare
```

Download and normalize ReFOCUS-Chart:

```bash
python scripts/download_refocus_chart.py \
  --local-dir /root/vqa_datasets/datasets/refocus_chart_hf

python scripts/prepare_refocus_chart.py \
  --raw-data-root /root/vqa_datasets/datasets/refocus_chart_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare
```

## 3. Run the fixed-tool-pool baselines

Use the VTool-R1 bbox tools that are wrapped in `tools/builtin_tools.py`.

Example chart tool pool:

```bash
CHART_TOOLS="focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw"
```

In `bash`, pass the tool names as plain positional arguments. Do not use `${=CHART_TOOLS}`, which is `zsh` syntax.

Example table tool pool:

```bash
TABLE_TOOLS="focus_on_columns_with_mask focus_on_rows_with_mask focus_on_columns_with_draw focus_on_rows_with_draw"
```

ChartQA:

```bash
python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root /root/VTool-R1/ChartQA/ChartQA\ Dataset \
  --normalized-data-root ./datasets/structured_vtoolr1_compare \
  --subset-id vtoolr1_chartqa_api_same_tools_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 200 \
  --held-out-limit 500 \
  --fixed-tool-names focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

ReFOCUS-Chart:

```bash
python scripts/run_structured_experiment.py \
  --dataset refocus_chart \
  --raw-data-root /root/vqa_datasets/datasets/refocus_chart_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare \
  --subset-id vtoolr1_refocus_chart_api_same_tools_v1 \
  --evolve-split train \
  --held-out-split test \
  --train-subset-size 200 \
  --held-out-limit 826 \
  --fixed-tool-names focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

ReFOCUS-TableVQA:

```bash
python scripts/run_structured_experiment.py \
  --dataset refocus_tablevqa \
  --raw-data-root /root/vqa_datasets/datasets/refocus_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare \
  --subset-id vtoolr1_tablevqa_api_same_tools_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 200 \
  --held-out-limit 304 \
  --fixed-tool-names focus_on_columns_with_mask focus_on_rows_with_mask focus_on_columns_with_draw focus_on_rows_with_draw \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

The key row for the main table is `skill_only_frozen_inference`.

## 3A. Local Qwen2.5-VL-32B sanity check on Refocus_Chart

We also ran a larger local backbone through a remote `vLLM` endpoint for a quick same-benchmark check:

- model: `Qwen2.5-VL-32B-Instruct`
- split: full `test` (`826`)
- `direct_vlm`: `67.43%` (`557 / 826`)
- handwritten `skill + bbox tools`: `49.64%` (`410 / 826`)

Result note:

- the handwritten `skill + tool` stack underperformed the direct model
- this suggests the current handwritten SOP/tool orchestration is weaker than the base model on this benchmark
- the result should be treated as a manual baseline, not as a competitive row against `VTool-R1`
- a later per-case probe showed the dominant handwritten failure modes were `empty_answer` and `tool_guided_wrong_answer`, while `direct_vlm` was hurt more by long or truncated responses than by pure visual failure

See:

- [docs/REFOCUS_CHART_QWEN32B_RESULTS.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_QWEN32B_RESULTS.md)
- [docs/reports/refocus_chart_qwen32b_results.json](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/reports/refocus_chart_qwen32b_results.json)
- [docs/REFOCUS_CHART_PROBE.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_PROBE.md)

The handwritten `Refocus_Chart` capability inventory itself is documented in:

- `Manual Capability Inventory` section inside [docs/REFOCUS_CHART_QWEN32B_RESULTS.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_QWEN32B_RESULTS.md)

## 4. Store the VTool-R1 reported reference

Create one small JSON file per dataset with the reported metric, for example:

```json
{
  "accuracy": 0.717,
  "source": "VTool-R1 paper / official repo"
}
```

Recommended paths:

- `/root/VTool-R1/results/chartqa_vtool_r1_reported.json`
- `/root/VTool-R1/results/refocus_chart_vtool_r1_reported.json`
- `/root/VTool-R1/results/refocus_tablevqa_vtool_r1_reported.json`

## 5. Merge into one comparison payload

ChartQA:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset chartqa \
  --our-summary artifacts/structured_benchmarks/vtoolr1_chartqa_api_same_tools_v1/summary.json \
  --vtool-result /root/VTool-R1/results/chartqa_vtool_r1_reported.json \
  --our-setting skill_only_frozen_inference \
  --reference-label vtool_r1_reported \
  --output artifacts/vtool_r1_comparison/chartqa_api_compare.json
```

ReFOCUS-Chart:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset refocus_chart \
  --our-summary artifacts/structured_benchmarks/vtoolr1_refocus_chart_api_same_tools_v1/summary.json \
  --vtool-result /root/VTool-R1/results/refocus_chart_vtool_r1_reported.json \
  --our-setting skill_only_frozen_inference \
  --reference-label vtool_r1_reported \
  --output artifacts/vtool_r1_comparison/refocus_chart_api_compare.json
```

ReFOCUS-TableVQA:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset refocus_tablevqa \
  --our-summary artifacts/structured_benchmarks/vtoolr1_tablevqa_api_same_tools_v1/summary.json \
  --vtool-result /root/VTool-R1/results/refocus_tablevqa_vtool_r1_reported.json \
  --our-setting skill_only_frozen_inference \
  --reference-label vtool_r1_reported \
  --output artifacts/vtool_r1_comparison/refocus_tablevqa_api_compare.json
```

The merged payload records:

- direct API baseline
- same-tool prompt baseline
- our same-tool evolve result
- `VTool-R1` reported reference
- non-secret API runtime metadata from our `summary.json`
