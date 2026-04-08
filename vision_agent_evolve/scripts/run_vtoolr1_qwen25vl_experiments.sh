#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH=".:${PYTHONPATH:-}"

export VLM_BASE_URL="${VLM_BASE_URL:-https://openrouter.ai/api/v1}"
if [[ -z "${VLM_API_KEY:-}" && -n "${OPENROUTER_API_KEY:-}" ]]; then
  export VLM_API_KEY="$OPENROUTER_API_KEY"
fi
export VLM_MODEL="${VLM_MODEL:-qwen/qwen2.5-vl-32b-instruct}"
unset VLM_API_STYLE VLM_USER_ID VLM_ACCESS_KEY VLM_QUOTA_ID

if [[ -z "${VLM_API_KEY:-}" ]]; then
  echo "VLM_API_KEY is not set. Set OPENROUTER_API_KEY or VLM_API_KEY before running." >&2
  exit 2
fi

SCALE="${SCALE:-smoke}"          # smoke | formal
MODE="${MODE:-same_tools}"       # official_tooluse | same_tools | full_evolve | all
DATASET="${DATASET:-all}"        # chartqa | tablevqa | all
NORMALIZED_ROOT="${NORMALIZED_ROOT:-./datasets/structured_vtoolr1_qwen25vl}"
VTOOL_ROOT="${VTOOL_ROOT:-/root/VTool-R1}"
REFOCUS_ROOT="${REFOCUS_ROOT:-/root/vqa_datasets/datasets/refocus_hf}"
OFFICIAL_WORKERS="${OFFICIAL_WORKERS:-8}"

if [[ "$SCALE" == "smoke" ]]; then
  TRAIN_SIZE="${TRAIN_SIZE:-20}"
  HELD_OUT_LIMIT="${HELD_OUT_LIMIT:-50}"
  ROUND_LIMIT="${ROUND_LIMIT:-2}"
  OFFICIAL_LIMIT="${OFFICIAL_LIMIT:-20}"
  SUBSET_SUFFIX="smoke_v1"
elif [[ "$SCALE" == "formal" ]]; then
  TRAIN_SIZE="${TRAIN_SIZE:-200}"
  HELD_OUT_LIMIT="${HELD_OUT_LIMIT:-0}"
  ROUND_LIMIT="${ROUND_LIMIT:-5}"
  OFFICIAL_LIMIT="${OFFICIAL_LIMIT:-0}"
  SUBSET_SUFFIX="formal_v1"
else
  echo "Unknown SCALE=$SCALE; expected smoke or formal." >&2
  exit 2
fi

python scripts/prepare_vtoolr1_qwen25vl.py \
  --vtool-root "$VTOOL_ROOT" \
  --refocus-root "$REFOCUS_ROOT" \
  --normalized-data-root "$NORMALIZED_ROOT"

run_structured() {
  local dataset="$1"
  local subset_id="$2"
  shift 2
  python scripts/run_structured_experiment.py \
    --dataset "$dataset" \
    --raw-data-root "$VTOOL_ROOT" \
    --normalized-data-root "$NORMALIZED_ROOT" \
    --subset-id "$subset_id" \
    --evolve-split train \
    --held-out-split test \
    --train-subset-size "$TRAIN_SIZE" \
    --held-out-limit "$HELD_OUT_LIMIT" \
    --max-planning-rounds "$ROUND_LIMIT" \
    --representatives-per-cluster 2 \
    --families-per-round-limit 2 \
    --tool-preference prefer_tools \
    "$@"
}

run_official_tooluse() {
  local dataset="$1"
  local subset_id="$2"
  python scripts/run_vtoolr1_official_tooluse_baseline.py \
    --dataset "$dataset" \
    --normalized-data-root "$NORMALIZED_ROOT" \
    --split test \
    --limit "$OFFICIAL_LIMIT" \
    --subset-id "$subset_id" \
    --vtool-root "$VTOOL_ROOT" \
    --workers "$OFFICIAL_WORKERS"
}

run_chartqa_official_tooluse() {
  run_official_tooluse chartqa "vtoolr1_qwen25vl32b_chart_official_tooluse_${SUBSET_SUFFIX}"
}

run_tablevqa_official_tooluse() {
  run_official_tooluse refocus_tablevqa "vtoolr1_qwen25vl32b_table_official_tooluse_${SUBSET_SUFFIX}"
}

run_chartqa_same_tools() {
  run_structured chartqa "vtoolr1_qwen25vl_chart_${SUBSET_SUFFIX}" \
    --fixed-tool-names \
      focus_on_x_values_with_mask focus_on_y_values_with_mask \
      focus_on_x_values_with_draw focus_on_y_values_with_draw \
    --disable-generated-tools \
    --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
}

run_tablevqa_same_tools() {
  run_structured refocus_tablevqa "vtoolr1_qwen25vl_table_${SUBSET_SUFFIX}" \
    --fixed-tool-names \
      focus_on_columns_with_mask focus_on_rows_with_mask \
      focus_on_columns_with_draw focus_on_rows_with_draw \
    --disable-generated-tools \
    --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
}

run_chartqa_full_evolve() {
  run_structured chartqa "vtoolr1_qwen25vl_chart_full_evolve_${SUBSET_SUFFIX}" \
    --settings direct_vlm agent_train_adaptive frozen_inference
}

run_tablevqa_full_evolve() {
  run_structured refocus_tablevqa "vtoolr1_qwen25vl_table_full_evolve_${SUBSET_SUFFIX}" \
    --settings direct_vlm agent_train_adaptive frozen_inference
}

run_selected() {
  local name="$1"
  local fn="$2"
  if [[ "$DATASET" == "all" || "$DATASET" == "$name" ]]; then
    "$fn"
  fi
}

if [[ "$MODE" == "official_tooluse" || "$MODE" == "all" ]]; then
  run_selected chartqa run_chartqa_official_tooluse
  run_selected tablevqa run_tablevqa_official_tooluse
fi

if [[ "$MODE" == "same_tools" || "$MODE" == "all" ]]; then
  run_selected chartqa run_chartqa_same_tools
  run_selected tablevqa run_tablevqa_same_tools
fi

if [[ "$MODE" == "full_evolve" || "$MODE" == "all" ]]; then
  run_selected chartqa run_chartqa_full_evolve
  run_selected tablevqa run_tablevqa_full_evolve
fi
