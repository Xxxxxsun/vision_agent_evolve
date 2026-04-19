# Structured Benchmark Commands

This file collects the current commands for:

- dataset preparation
- subset-level evolve
- frozen evaluation
- direct VLM baselines
- direct-vs-agent debugging

All commands assume:

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export PYTHONPATH=.
```

If needed, also set your model endpoint first:

```bash
export VLM_BASE_URL="..."
export VLM_API_KEY="..."
export VLM_MODEL="..."
```

For the Alibaba internal chat route used in recent runs:

```bash
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_USER_ID="506759"
export VLM_ACCESS_KEY="9101ac974ab20f60f668dcf099bc6a10"
export VLM_QUOTA_ID="dd95187c-29dd-464d-9b96-8f62e6ab8eb5"
export VLM_APP="model_train_vlm"
```

## 0. Materialize Stable Local Raw Data

The helper below downloads Hugging Face benchmark data into stable local directories under
`/root/vqa_datasets/datasets/...`, so later experiments do not depend on transient cache paths.

```bash
python scripts/materialize_hf_benchmark_data.py --dataset chartqa --chartqa-splits val
python scripts/materialize_hf_benchmark_data.py --dataset hrbench
python scripts/materialize_hf_benchmark_data.py --dataset mathvista --mathvista-splits testmini
```

Resulting raw roots used by the current repo:

- `ChartQA`: `/root/vqa_datasets/datasets/chartqa_hf`
- `HRBench`: `/root/vqa_datasets/datasets/hr_bench`
- `MathVista`: `/root/vqa_datasets/datasets/mathvista`

## GTA Official Formal Run

For strict GTA-aligned formal runs, use the dedicated workflow in [GTA_OFFICIAL_EXPERIMENT.md](/root/vision_agent_evolve/vision_agent_evolve/docs/GTA_OFFICIAL_EXPERIMENT.md).

If the run will happen on a separate GPU instance, use [GTA_GPU_INSTANCE_RUNBOOK.md](/root/vision_agent_evolve/vision_agent_evolve/docs/GTA_GPU_INSTANCE_RUNBOOK.md) as the operational checklist.

Quick entry points:

```bash
python scripts/check_gta_official_setup.py --mode server --server-url "$VISION_AGENT_GTA_TOOL_SERVER" --repo-root "$VISION_AGENT_GTA_OFFICIAL_REPO" --require-keys
```

```bash
bash scripts/start_gta_official_tool_server.sh
```

```bash
bash scripts/run_gta_official_formal.sh gta_official_formal_v1
```

## 1. ChartQA

### 1.1 Evolve on train subset and evaluate on val

```bash
python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root "/root/vqa_datasets/datasets/chartqa_official/ChartQA Dataset" \
  --normalized-data-root "./datasets/structured_chartqa" \
  --subset-id chartqa_train25_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 25 \
  --held-out-limit 200 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference
```

### 1.2 Train only

```bash
python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root "/root/vqa_datasets/datasets/chartqa_official/ChartQA Dataset" \
  --normalized-data-root "./datasets/structured_chartqa" \
  --subset-id chartqa_train25_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 25 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive
```

### 1.3 Frozen eval on full val

ChartQA val size is `1920`.

```bash
python scripts/eval_structured_frozen.py \
  --dataset chartqa \
  --raw-data-root "/root/vqa_datasets/datasets/chartqa_official/ChartQA Dataset" \
  --normalized-data-root "./datasets/structured_chartqa" \
  --subset-id chartqa_train25_v1 \
  --held-out-split val
```

### 1.4 Direct GPT-4o on full val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root "/root/vqa_datasets/datasets/chartqa_hf" \
  --normalized-data-root "./datasets/structured_chartqa" \
  --subset-id chartqa_reasoned_gpt4o_val_full_v3 \
  --evolve-split val \
  --train-subset-size 1920 \
  --settings reasoned_vlm
```

### 1.5 Function-calling + skills

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root "/root/vqa_datasets/datasets/chartqa_hf" \
  --normalized-data-root "./datasets/structured_chartqa" \
  --subset-id chartqa_fc_gpt4o_val_full_v4 \
  --evolve-split val \
  --train-subset-size 1920 \
  --settings function_calling_vqa
```

## 2. HRBench4K

### 2.1 Prepare / refresh normalized files

This reuses cached `_assets/hrbench` PNGs if they already exist.

```bash
python scripts/prepare_hrbench.py \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench
```

### 2.2 Evolve on train subset and evaluate on full val

HRBench normalized split is `train=100`, `val=700`.

```bash
python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench4k_train100_v2 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 100 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference
```

### 2.3 Train only

```bash
python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench4k_train100_v2 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 100 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive
```

### 2.4 Direct GPT-4o on full val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_reasoned_gpt4o_val_full_v3 \
  --evolve-split val \
  --train-subset-size 700 \
  --settings reasoned_vlm
```

### 2.5 Function-calling + skills

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_fc_gpt4o_val_full_v4 \
  --evolve-split val \
  --train-subset-size 700 \
  --settings function_calling_vqa
```

### 2.6 Frozen eval only

```bash
python scripts/eval_structured_frozen.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench4k_train100_v2 \
  --held-out-split val
```

### 2.7 Test the manually added HRBench tool directly

```bash
export VISION_AGENT_LEARNED_DIR=learned/hrbench4k_train100_v1/active
python -m tools hrbench_focus_grid_tool /path/to/one/hrbench/image.jpg
```

## 3. VStar

### 3.1 Prepare

```bash
python scripts/prepare_vstar.py \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --train-size 40 \
  --val-size 151
```

### 3.2 Evolve + frozen

```bash
python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_train40_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 40 \
  --held-out-limit 151 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference
```

### 3.3 Reasoned VLM on full val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_reasoned_gpt4o_val_full_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --settings reasoned_vlm
```

### 3.4 Function-calling VQA on full val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_fc_gpt4o_val_full_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --settings function_calling_vqa
```

```bash
VLM_MODEL="gpt-5.4-0305-global" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_fc_gpt54_val_full_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --settings function_calling_vqa
```

### 3.5 Function-calling VQA with hierarchical skills

This uses the new prompt-routing skill layer documented in
[FUNCTION_CALLING_SKILLS.md](/root/vision_agent_evolve/vision_agent_evolve/docs/FUNCTION_CALLING_SKILLS.md).

```bash
VLM_MODEL="gpt-5.4-0305-global" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_fc_skills_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --settings function_calling_vqa
```

To use an alternate learned/static skill root:

```bash
VLM_MODEL="gpt-5.4-0305-global" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_fc_skills_customroot_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --capability-root ./learned/my_skill_pack \
  --settings function_calling_vqa
```

To disable the skill router and run the plain function-calling baseline:

```bash
VLM_MODEL="gpt-5.4-0305-global" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_fc_noskills_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --disable-skills \
  --settings function_calling_vqa
```

To run the pure-skill variant without exposing any tools:

```bash
VLM_MODEL="gpt-5.4-0305-global" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_fc_skill_only_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --disable-fc-tools \
  --settings function_calling_vqa
```

### 3.5 Reasoned vs function-calling with Alibaba proxy

Use the HAL-style proxy credentials when testing `function_calling_vqa` against the Alibaba gateway. In local experiments, the original `llm_application` credentials frequently produced proxy errors or policy blocks on tool-calling requests, while the HAL defaults allowed the same requests to complete.

```bash
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_MODEL="gpt-5.4-0305-global"

export VLM_USER_ID="506759"
export VLM_ACCESS_KEY="9101ac974ab20f60f668dcf099bc6a10"
export VLM_QUOTA_ID="dd95187c-29dd-464d-9b96-8f62e6ab8eb5"
export VLM_APP="model_train_vlm"

python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_val151_reasoned_vs_fc_gpt54_alibaba_halcreds_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --held-out-limit 0 \
  --settings reasoned_vlm function_calling_vqa
```

Notes:

- `reasoned_vlm` is now the preferred no-tool baseline for VStar. It asks the model to reason briefly before returning `Final answer: <answer>`.
- `function_calling_vqa` now supports `vstar`, `chartqa`, `mathvista`, and `hrbench`.
- The current VStar tool prompt encourages `zoom_image` for small-object attribute questions.
- `artifact_production_rate` is the reliable signal for visual tool use. `tool_usage_rate` still follows the older bash-tool extraction logic and can under-report runtime-native tool calls.
```

## 6. Current Results Snapshot

### 6.1 GPT-4o

| Benchmark | Setting | Accuracy | Notes |
| --- | --- | ---: | --- |
| ChartQA | `reasoned_vlm` | `0.7552` | `1450 / 1920` |
| ChartQA | `function_calling_vqa` | `0.7693` | `1477 / 1920` |
| MathVista | `reasoned_vlm` | `0.6711` | `604 / 900` |
| MathVista | `function_calling_vqa` | `0.6922` | `623 / 900` |
| HRBench | `reasoned_vlm` | `0.6386` | `447 / 700` |
| HRBench | `function_calling_vqa` | `0.6414` | `449 / 700` |
| VStar | `reasoned_vlm` | `0.5828` | `88 / 151` |

### 6.2 GPT-5.4 on VStar

| Setting | Accuracy | Direct Attributes | Relative Position | Tool Usage |
| --- | ---: | ---: | ---: | ---: |
| `reasoned_vlm` | `0.7748` | `0.7174` | `0.8644` | `0.0000` |
| `function_calling_vqa` | `0.7881` | `0.8043` | `0.7627` | `0.5695` artifact rate |
| `function_calling_vqa + skills` | `0.7947` | `0.7826` | `0.8136` | `0.5960` |
| `function_calling_vqa + no-tool skill` | `0.7086` | `0.6522` | `0.7966` | `0.0000` |

Reference summaries:

- `artifacts/structured_benchmarks/chartqa_reasoned_gpt4o_val_full_v3/summary.json`
- `artifacts/structured_benchmarks/chartqa_fc_gpt4o_val_full_v4/summary.json`
- `artifacts/structured_benchmarks/mathvista_reasoned_gpt4o_val_full_v2/summary.json`
- `artifacts/structured_benchmarks/mathvista_fc_gpt4o_val_full_v3/summary.json`
- `artifacts/structured_benchmarks/hrbench_reasoned_gpt4o_val_full_v3/summary.json`
- `artifacts/structured_benchmarks/hrbench_fc_gpt4o_val_full_v4/summary.json`
- `artifacts/structured_benchmarks/vstar_reasoned_gpt4o_val_full_v2/summary.json`
- `artifacts/structured_benchmarks/vstar_val151_reasoned_only_vlmevalalign_gpt54_alibaba_halcreds_v6/summary.json`
- `artifacts/structured_benchmarks/vstar_val151_fc_only_vlmevalalign_gpt54_alibaba_halcreds_v6/summary.json`
- `artifacts/structured_benchmarks/vstar_fc_skills_gpt54_val151_rerun_v1/summary.json`
- `artifacts/structured_benchmarks/vstar_notool_skill_gpt54_val151_v1/summary.json`

## 4. TextVQA

### 4.1 Prepare

```bash
python scripts/prepare_textvqa.py \
  --raw-data-root /root/vqa_datasets/datasets/textvqa \
  --normalized-data-root ./datasets/structured_multibench
```

### 4.2 Evolve + frozen

```bash
python scripts/run_structured_experiment.py \
  --dataset textvqa \
  --raw-data-root /root/vqa_datasets/datasets/textvqa \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id textvqa_train100_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 100 \
  --held-out-limit 200 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference balanced \
  --settings agent_train_adaptive frozen_inference
```

### 4.3 Direct GPT-4o on val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset textvqa \
  --raw-data-root /root/vqa_datasets/datasets/textvqa \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id textvqa_direct_gpt4o_val_v1 \
  --evolve-split val \
  --train-subset-size 200 \
  --settings direct_vlm
```

### 4.4 Direct GPT-4o on train subset for comparison

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset textvqa \
  --raw-data-root /root/vqa_datasets/datasets/textvqa \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id textvqa_direct_train100_v1 \
  --evolve-split train \
  --train-subset-size 100 \
  --settings direct_vlm
```

### 4.5 Debug direct vs empty-active agent

```bash
python scripts/debug_direct_vs_agent.py \
  --dataset textvqa \
  --normalized-data-root ./datasets/structured_multibench \
  --split train \
  --limit 20 \
  --output-dir artifacts/debug_compare/textvqa_train20_compare_promptfix_v1
```

Single-case version:

```bash
python scripts/debug_direct_vs_agent.py \
  --dataset textvqa \
  --normalized-data-root ./datasets/structured_multibench \
  --split train \
  --case-id <case_id> \
  --output-dir artifacts/debug_compare/textvqa_single_case_v1
```

## 5. MathVista

### 5.1 Unzip images first

Current raw download includes `images.zip`, and images must be extracted before normalization.

```bash
cd /root/vqa_datasets/datasets/mathvista
unzip -q -o images.zip
find . -path '*images/1.jpg' | head
```

Then return to the repo:

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export PYTHONPATH=.
```

### 5.2 Prepare

Smoke test:

```bash
python scripts/prepare_mathvista.py \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --limit 5
```

Full normalize:

```bash
python scripts/prepare_mathvista.py \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench
```

### 5.3 Evolve + frozen

MathVista now uses deterministic scoring first, then an LLM judge fallback for free-form answers that do not pass the rule-based check.

Use a fresh subset id after a crash:

```bash
python scripts/run_structured_experiment.py \
  --dataset mathvista \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_train100_v2 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 100 \
  --held-out-limit 200 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference
```

### 5.4 Reasoned GPT-4o on val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset mathvista \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_reasoned_gpt4o_val_full_v2 \
  --evolve-split val \
  --train-subset-size 900 \
  --settings reasoned_vlm
```

### 5.5 Function-calling + skills

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset mathvista \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_fc_gpt4o_val_full_v3 \
  --evolve-split val \
  --train-subset-size 900 \
  --settings function_calling_vqa
```

## 6. GTA

Assumes the GTA raw directory contains:

- `dataset.json`
- `toolmeta.json`
- `image/`

### 6.1 Prepare

```bash
python scripts/prepare_gta.py \
  --raw-data-root /path/to/gta_dataset \
  --normalized-data-root ./datasets/structured_multibench \
  --train-ratio 0.3 \
  --seed 42
```

### 6.2 Evolve + frozen

```bash
python scripts/run_structured_experiment.py \
  --dataset gta \
  --raw-data-root /path/to/gta_dataset \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id gta_train51_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 51 \
  --held-out-limit 121 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference
```

### 6.3 Frozen eval only

```bash
python scripts/eval_structured_frozen.py \
  --dataset gta \
  --raw-data-root /path/to/gta_dataset \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id gta_train51_v1 \
  --held-out-split val
```

## 7. Generic frozen eval command

Use this when you already have a learned subset and just want held-out frozen evaluation:

```bash
python scripts/eval_structured_frozen.py \
  --dataset <dataset_name> \
  --raw-data-root <raw_data_root> \
  --normalized-data-root <normalized_root> \
  --subset-id <subset_id> \
  --held-out-split val \
  --held-out-limit <optional_limit>
```

## 8. Quick result checks

### 8.1 Summary

```bash
cat artifacts/structured_benchmarks/<subset_id>/summary.json
```

### 8.2 First evolve rounds

```bash
cat artifacts/structured_benchmarks/<subset_id>/first_10_evolves.json
```

### 8.3 Active capabilities

```bash
find learned/<subset_id>/active -maxdepth 4 | sort
```

### 8.4 Per-case rows

```bash
tail -n 20 artifacts/structured_benchmarks/<subset_id>/per_case.jsonl
```

## 9. Useful counts

```bash
wc -l datasets/structured_chartqa/chartqa/train.jsonl
wc -l datasets/structured_chartqa/chartqa/val.jsonl
wc -l datasets/structured_multibench/hrbench/train.jsonl
wc -l datasets/structured_multibench/hrbench/val.jsonl
wc -l datasets/structured_multibench/vstar/train.jsonl
wc -l datasets/structured_multibench/vstar/val.jsonl
wc -l datasets/structured_multibench/textvqa/train.jsonl
wc -l datasets/structured_multibench/textvqa/val.jsonl
wc -l datasets/structured_multibench/mathvista/train.jsonl
wc -l datasets/structured_multibench/mathvista/val.jsonl
wc -l datasets/structured_multibench/gta/train.jsonl
wc -l datasets/structured_multibench/gta/val.jsonl
```
