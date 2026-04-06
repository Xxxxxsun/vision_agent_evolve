# VTool-R1 API Comparison Workflow

This workflow is for the no-GPU setting:

- use this repo's self-evolution framework
- call a VLM through the existing Alibaba/OpenAI-compatible proxy path
- keep the `VTool-R1` tool protocol fixed
- disable new tool generation
- compare against `VTool-R1` as a reported reference

It is not a same-backbone reproduction of `VTool-R1`. It is a strict same-benchmark, same-tool-pool, training-free API evaluation line.

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

## 3. Run the fixed-tool-pool baselines

Use the VTool-R1 bbox tools that are wrapped in `tools/builtin_tools.py`.

Example chart tool pool:

```bash
CHART_TOOLS="focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw"
```

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
  --fixed-tool-names ${=CHART_TOOLS} \
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
  --fixed-tool-names ${=TABLE_TOOLS} \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

The key row for the main table is `skill_only_frozen_inference`.

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
