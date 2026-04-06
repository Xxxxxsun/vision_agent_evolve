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

## GTA Official Formal Run

For strict GTA-aligned formal runs, use the dedicated workflow in [GTA_OFFICIAL_EXPERIMENT.md](/root/vision_agent_evolve/vision_agent_evolve/docs/GTA_OFFICIAL_EXPERIMENT.md).

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
  --raw-data-root "/root/vqa_datasets/datasets/chartqa_official/ChartQA Dataset" \
  --normalized-data-root "./datasets/structured_chartqa" \
  --subset-id chartqa_direct_gpt4o_val_full_v1 \
  --evolve-split val \
  --train-subset-size 1920 \
  --settings direct_vlm
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
  --subset-id hrbench_direct_gpt4o_val_full_v2 \
  --evolve-split val \
  --train-subset-size 700 \
  --settings direct_vlm
```

### 2.5 Frozen eval only

```bash
python scripts/eval_structured_frozen.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench4k_train100_v2 \
  --held-out-split val
```

### 2.6 Test the manually added HRBench tool directly

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

### 3.3 Direct GPT-4o on full val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_direct_gpt4o_val_full_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --settings direct_vlm
```

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

### 5.4 Direct GPT-4o on val

```bash
VLM_MODEL="gpt-4o" python scripts/run_structured_experiment.py \
  --dataset mathvista \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_direct_gpt4o_val_v1 \
  --evolve-split val \
  --train-subset-size 200 \
  --settings direct_vlm
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
