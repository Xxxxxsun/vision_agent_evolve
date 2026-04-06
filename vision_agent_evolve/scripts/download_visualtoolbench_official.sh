#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-$ROOT_DIR/datasets/visualtoolbench_official}"

mkdir -p "$TARGET_DIR"

hf download ScaleAI/VisualToolBench \
  --repo-type dataset \
  --local-dir "$TARGET_DIR"

echo "Downloaded official VisualToolBench dataset to: $TARGET_DIR"
