# ChartQA Demo

This repo now includes a tiny local ChartQA-style demo dataset under [datasets/chartqa_demo/raw](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/datasets/chartqa_demo/raw).

## 1. Use OpenAI-compatible API

```bash
export OPENAI_API_KEY="YOUR_OPENAI_KEY"
export OPENAI_MODEL="gpt-4o"
```

Or use the repo-native names:

```bash
export VLM_BASE_URL="https://api.openai.com/v1"
export VLM_API_KEY="YOUR_OPENAI_KEY"
export VLM_MODEL="gpt-4o"
```

## 2. Normalize the demo dataset

```bash
.venv/bin/python scripts/prepare_chartqa.py \
  --raw-data-root datasets/chartqa_demo/raw \
  --normalized-data-root datasets/structured
```

This writes:

- `datasets/structured/chartqa/train.jsonl`
- `datasets/structured/chartqa/val.jsonl`

## 3. Run the structured experiment on 2 train examples

```bash
.venv/bin/python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root datasets/chartqa_demo/raw \
  --normalized-data-root datasets/structured \
  --subset-id chartqa_refocus_demo \
  --evolve-split train \
  --held-out-split val \
  --k 2 \
  --max-attempts 2
```

Outputs go to:

- `artifacts/structured_benchmarks/chartqa_refocus_demo/per_case.jsonl`
- `artifacts/structured_benchmarks/chartqa_refocus_demo/summary.json`

## 4. Re-run frozen transfer only

```bash
.venv/bin/python scripts/eval_structured_frozen.py \
  --dataset chartqa \
  --raw-data-root datasets/chartqa_demo/raw \
  --normalized-data-root datasets/structured \
  --subset-id chartqa_refocus_demo \
  --snapshot-name chartqa_refocus_demo_train_k2_snapshot \
  --held-out-split val
```

## Notes

- The demo is intentionally tiny: 2 train examples and 1 val example.
- If you only want to verify the data path first, step 2 is enough.
- If OpenAI env vars are missing, the experiment scripts will fail when they first call the model.
