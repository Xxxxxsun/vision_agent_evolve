#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_ROOT="${1:-$ROOT_DIR/datasets/tirbench_official}"
NORMALIZED_ROOT="${2:-$ROOT_DIR/datasets/structured_multibench}"
OUTPUT_ROOT="${3:-$ROOT_DIR/artifacts}"
LIMIT="${TIR_LIMIT:-0}"
SOLVER_MODEL="${TIR_SOLVER_MODEL:-o4-mini}"
EXTRACTOR_MODEL="${TIR_EXTRACTOR_MODEL:-o4-mini}"
MODE="${TIR_MODE:-direct}"

python "$ROOT_DIR/scripts/prepare_tirbench.py" \
  --raw-data-root "$RAW_ROOT" \
  --normalized-data-root "$NORMALIZED_ROOT"

suffix="$MODE"
if [[ "$LIMIT" != "0" ]]; then
  suffix="${suffix}_${LIMIT}"
fi

python "$ROOT_DIR/scripts/eval_tirbench.py" \
  --normalized-data-root "$NORMALIZED_ROOT" \
  --mode "$MODE" \
  --limit "$LIMIT" \
  --solver-model "$SOLVER_MODEL" \
  --extractor-model "$EXTRACTOR_MODEL" \
  --output-dir "$OUTPUT_ROOT/tirbench_${suffix}_${SOLVER_MODEL}_extract_${EXTRACTOR_MODEL}"
