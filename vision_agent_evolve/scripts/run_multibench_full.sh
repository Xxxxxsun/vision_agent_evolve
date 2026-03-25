#!/usr/bin/env bash
set -euo pipefail

cd ~/vision_agent_evolve/vision_agent_evolve

# ========================================
# 0. Environment
# ========================================
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH=.
export HF_HOME=/root/.cache/huggingface
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

# Replace these with your real values or export them before running.
export VLM_BASE_URL="${VLM_BASE_URL:-https://YOUR_VLM_BASE_URL}"
export VLM_API_KEY="${VLM_API_KEY:-YOUR_VLM_API_KEY}"
export VLM_MODEL="${VLM_MODEL:-YOUR_VLM_MODEL}"

# Optional: only needed if the dataset mirror requires auth.
export HF_TOKEN="${HF_TOKEN:-}"

mkdir -p logs
mkdir -p /root/vqa_datasets/datasets

echo "========================================"
echo "Environment"
echo "========================================"
echo "PWD=$PWD"
echo "VLM_BASE_URL=$VLM_BASE_URL"
echo "VLM_MODEL=$VLM_MODEL"
echo "HF_ENDPOINT=$HF_ENDPOINT"

# ========================================
# 1. Install dependencies
# ========================================
python -m pip install -U pip
python -m pip install -U datasets huggingface_hub pyarrow pillow

if [ -n "${HF_TOKEN}" ]; then
  huggingface-cli login --token "$HF_TOKEN"
fi

# ========================================
# 2. Download datasets
# ========================================
echo "========================================"
echo "Downloading datasets"
echo "========================================"

huggingface-cli download lmms-lab/vstar-bench \
  --repo-type dataset \
  --local-dir /root/vqa_datasets/datasets/vstar_bench

huggingface-cli download DreamMr/HR-Bench \
  --repo-type dataset \
  --local-dir /root/vqa_datasets/datasets/hr_bench

huggingface-cli download AI4Math/MathVista \
  --repo-type dataset \
  --local-dir /root/vqa_datasets/datasets/mathvista

huggingface-cli download lmms-lab/textvqa \
  --repo-type dataset \
  --local-dir /root/vqa_datasets/datasets/textvqa

echo "========================================"
echo "Dataset checks"
echo "========================================"
find /root/vqa_datasets/datasets/vstar_bench -maxdepth 3 | head -n 20 || true
find /root/vqa_datasets/datasets/hr_bench -maxdepth 3 | head -n 20 || true
find /root/vqa_datasets/datasets/mathvista -maxdepth 3 | head -n 20 || true
find /root/vqa_datasets/datasets/textvqa -maxdepth 3 | head -n 20 || true

# ========================================
# 3. Normalize datasets
# ========================================
echo "========================================"
echo "Normalizing datasets"
echo "========================================"

python scripts/prepare_vstar.py \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --train-size 40 \
  --val-size 151 | tee logs/prepare_vstar.log

python scripts/prepare_hrbench.py \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --train-size 100 \
  --val-size 700 | tee logs/prepare_hrbench.log

python scripts/prepare_mathvista.py \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --train-size 100 \
  --val-size 900 | tee logs/prepare_mathvista.log

python scripts/prepare_textvqa.py \
  --raw-data-root /root/vqa_datasets/datasets/textvqa \
  --normalized-data-root ./datasets/structured_multibench | tee logs/prepare_textvqa.log

# ========================================
# 4. Train + Frozen Eval
# ========================================
echo "========================================"
echo "Running train adaptive + frozen inference"
echo "========================================"

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
  --settings agent_train_adaptive frozen_inference | tee logs/vstar_train_frozen.log

python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench4k_train100_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 100 \
  --held-out-limit 200 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference | tee logs/hrbench_train_frozen.log

python scripts/run_structured_experiment.py \
  --dataset mathvista \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_train100_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 100 \
  --held-out-limit 200 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference | tee logs/mathvista_train_frozen.log

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
  --tool-preference prefer_tools \
  --settings agent_train_adaptive frozen_inference | tee logs/textvqa_train_frozen.log

# ========================================
# 5. Direct VLM on VAL only
# ========================================
echo "========================================"
echo "Running direct VLM on held-out val"
echo "========================================"

python scripts/run_structured_experiment.py \
  --dataset vstar \
  --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_direct_val151_v1 \
  --evolve-split val \
  --train-subset-size 151 \
  --settings direct_vlm | tee logs/vstar_direct_val.log

python scripts/run_structured_experiment.py \
  --dataset hrbench \
  --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_direct_val200_v1 \
  --evolve-split val \
  --train-subset-size 200 \
  --settings direct_vlm | tee logs/hrbench_direct_val.log

python scripts/run_structured_experiment.py \
  --dataset mathvista \
  --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_direct_val200_v1 \
  --evolve-split val \
  --train-subset-size 200 \
  --settings direct_vlm | tee logs/mathvista_direct_val.log

python scripts/run_structured_experiment.py \
  --dataset textvqa \
  --raw-data-root /root/vqa_datasets/datasets/textvqa \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id textvqa_direct_val200_v1 \
  --evolve-split val \
  --train-subset-size 200 \
  --settings direct_vlm | tee logs/textvqa_direct_val.log

# ========================================
# 6. Final comparison summary
# ========================================
echo "========================================"
echo "Final comparison"
echo "========================================"

python - <<'PY'
import json
from pathlib import Path

pairs = [
    ("vstar", "vstar_train40_v1", "vstar_direct_val151_v1"),
    ("hrbench", "hrbench4k_train100_v1", "hrbench_direct_val200_v1"),
    ("mathvista", "mathvista_train100_v1", "mathvista_direct_val200_v1"),
    ("textvqa", "textvqa_train100_v1", "textvqa_direct_val200_v1"),
]

base = Path("artifacts/structured_benchmarks")

for name, learned_id, direct_id in pairs:
    learned_path = base / learned_id / "summary.json"
    direct_path = base / direct_id / "summary.json"

    print("=" * 60)
    print(name)

    learned = json.loads(learned_path.read_text(encoding="utf-8"))
    direct = json.loads(direct_path.read_text(encoding="utf-8"))

    learned_train = learned["settings"].get("agent_train_adaptive", {}).get("accuracy", 0.0)
    learned_frozen = learned["settings"].get("frozen_inference", {}).get("accuracy", 0.0)
    direct_val = direct["settings"].get("direct_vlm", {}).get("accuracy", 0.0)

    print(f"train_adaptive_accuracy = {learned_train:.4f}")
    print(f"val_frozen_accuracy     = {learned_frozen:.4f}")
    print(f"val_direct_vlm_accuracy = {direct_val:.4f}")
    print(f"val_gain_over_direct    = {learned_frozen - direct_val:+.4f}")
    print(f"learned_summary         = {learned_path}")
    print(f"direct_summary          = {direct_path}")
PY

echo "========================================"
echo "Done"
echo "========================================"
