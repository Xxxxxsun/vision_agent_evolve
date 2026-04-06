#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DATA_ROOT="${1:-$ROOT_DIR/datasets/visualtoolbench_official}"
NORMALIZED_ROOT="${2:-$ROOT_DIR/datasets/structured_multibench}"
LIMIT="${3:-20}"
OUTPUT_DIR="${4:-artifacts/visualtoolbench_smoke20}"

cd "$ROOT_DIR"

python scripts/prepare_visualtoolbench.py \
  --raw-data-root "$RAW_DATA_ROOT" \
  --normalized-data-root "$NORMALIZED_ROOT" \
  --limit "$LIMIT"

python scripts/eval_visualtoolbench.py \
  --normalized-data-root "$NORMALIZED_ROOT" \
  --split test \
  --limit "$LIMIT" \
  --output-dir "$OUTPUT_DIR"
