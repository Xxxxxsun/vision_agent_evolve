#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH="${PYTHONPATH:-.}"
export VISION_AGENT_GTA_TOOL_MODE="${VISION_AGENT_GTA_TOOL_MODE:-approx_only}"
export VLM_API_STYLE="${VLM_API_STYLE:-alibaba_chat}"
export VLM_BASE_URL="${VLM_BASE_URL:-https://llm-chat-api.alibaba-inc.com/v1/api/chat}"
export VLM_MODEL="${VLM_MODEL:-gpt-5-0807}"

RAW_DATA_ROOT="${GTA_RAW_DATA_ROOT:-/root/vision_agent_evolve/datasets/GTA/opencompass/data/gta_dataset}"
NORMALIZED_DATA_ROOT="${GTA_NORMALIZED_DATA_ROOT:-./datasets/structured_multibench}"
BASELINE_SUBSET_ID="${GTA_BASELINE_SUBSET_ID:-gta_fallback_gpt5_0807_repro_v1}"
EVOLVE_SUBSET_ID="${GTA_EVOLVE_SUBSET_ID:-gta_fallback_gpt5_0807_evolve_v1}"
RUN_PHASE="${GTA_RUN_PHASE:-both}"
TRAIN_SUBSET_SIZE="${GTA_TRAIN_SUBSET_SIZE:-51}"
HELD_OUT_LIMIT="${GTA_HELD_OUT_LIMIT:-121}"

FIXED_TOOL_NAMES=(
  Calculator
  GoogleSearch
  Plot
  Solver
  OCR
  ImageDescription
  TextToBbox
  CountGivenObject
  MathOCR
  DrawBox
  AddText
  TextToImage
  ImageStylization
  RegionAttributeDescription
)

if [[ ! -f "${RAW_DATA_ROOT}/dataset.json" || ! -f "${RAW_DATA_ROOT}/toolmeta.json" || ! -d "${RAW_DATA_ROOT}/image" ]]; then
  echo "Missing GTA raw dataset under ${RAW_DATA_ROOT}" >&2
  echo "Expected dataset.json, toolmeta.json, and image/." >&2
  exit 1
fi

if [[ "${VLM_API_STYLE}" == "alibaba_chat" ]]; then
  export VLM_API_KEY="${VLM_API_KEY:-EMPTY}"
  if [[ -z "${VLM_USER_ID:-}" || -z "${VLM_ACCESS_KEY:-}" || -z "${VLM_QUOTA_ID:-}" ]]; then
    echo "Missing Alibaba chat API credentials." >&2
    echo "Set VLM_USER_ID, VLM_ACCESS_KEY, and VLM_QUOTA_ID." >&2
    exit 1
  fi
elif [[ -z "${VLM_BASE_URL:-}${OPENAI_BASE_URL:-}" || -z "${VLM_MODEL:-}${OPENAI_MODEL:-}" ]]; then
  echo "Missing VLM endpoint/model environment." >&2
  echo "Set VLM_BASE_URL and VLM_MODEL, or OPENAI_BASE_URL and OPENAI_MODEL." >&2
  exit 1
fi

run_experiment() {
  local subset_id="$1"
  shift
  python scripts/run_structured_experiment.py \
    --dataset gta \
    --raw-data-root "${RAW_DATA_ROOT}" \
    --normalized-data-root "${NORMALIZED_DATA_ROOT}" \
    --subset-id "${subset_id}" \
    --evolve-split train \
    --held-out-split val \
    --train-subset-size "${TRAIN_SUBSET_SIZE}" \
    --held-out-limit "${HELD_OUT_LIMIT}" \
    --tool-preference balanced \
    --fixed-tool-names "${FIXED_TOOL_NAMES[@]}" \
    --disable-generated-tools \
    --settings "$@"
}

case "${RUN_PHASE}" in
  baseline)
    run_experiment "${BASELINE_SUBSET_ID}" \
      direct_vlm pure_react toolpool_prompt_baseline same_tool_preset_tools_only
    ;;
  evolve)
    run_experiment "${EVOLVE_SUBSET_ID}" \
      direct_vlm pure_react toolpool_prompt_baseline same_tool_preset_tools_only \
      skill_only_train_adaptive skill_only_frozen_inference
    ;;
  both)
    run_experiment "${BASELINE_SUBSET_ID}" \
      direct_vlm pure_react toolpool_prompt_baseline same_tool_preset_tools_only
    run_experiment "${EVOLVE_SUBSET_ID}" \
      direct_vlm pure_react toolpool_prompt_baseline same_tool_preset_tools_only \
      skill_only_train_adaptive skill_only_frozen_inference
    ;;
  *)
    echo "Unknown GTA_RUN_PHASE=${RUN_PHASE}. Use baseline, evolve, or both." >&2
    exit 1
    ;;
esac
