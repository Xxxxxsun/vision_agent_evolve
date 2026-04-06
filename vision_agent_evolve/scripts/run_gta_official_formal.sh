#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH=.
export VISION_AGENT_GTA_TOOL_MODE=official_server
export VISION_AGENT_GTA_TOOL_SERVER="${VISION_AGENT_GTA_TOOL_SERVER:-http://127.0.0.1:16181}"

python scripts/check_gta_official_setup.py \
  --mode server \
  --server-url "${VISION_AGENT_GTA_TOOL_SERVER}" \
  --repo-root "${VISION_AGENT_GTA_OFFICIAL_REPO:-/tmp/GTA_official}" \
  --require-keys

python scripts/run_structured_experiment.py \
  --dataset gta \
  --raw-data-root /root/vision_agent_evolve/datasets/GTA/opencompass/data/gta_dataset \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id "${1:-gta_official_formal_v1}" \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size "${GTA_TRAIN_SUBSET_SIZE:-51}" \
  --held-out-limit "${GTA_HELD_OUT_LIMIT:-121}" \
  --tool-preference balanced \
  --fixed-tool-names Calculator GoogleSearch Plot Solver OCR ImageDescription TextToBbox CountGivenObject MathOCR DrawBox AddText TextToImage ImageStylization RegionAttributeDescription \
  --disable-generated-tools \
  --settings direct_vlm pure_react toolpool_prompt_baseline same_tool_preset_tools_only skill_only_train_adaptive skill_only_frozen_inference
