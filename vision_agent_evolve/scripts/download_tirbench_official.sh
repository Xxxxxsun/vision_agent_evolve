#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-$ROOT_DIR/datasets/tirbench_official}"

mkdir -p "$TARGET_DIR"

hf download Agents-X/TIR-Bench \
  TIR-Bench.json data.zip \
  --repo-type dataset \
  --local-dir "$TARGET_DIR"

python - <<'PY' "$TARGET_DIR"
import sys
import zipfile
from pathlib import Path

target = Path(sys.argv[1])
zip_path = target / "data.zip"
data_dir = target / "data"
if not zip_path.exists():
    raise SystemExit(f"Missing {zip_path}")
if data_dir.exists():
    print(f"Images already extracted at {data_dir}")
else:
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(target)
    print(f"Extracted images to {data_dir}")
PY

echo "Downloaded official TIR-Bench dataset to: $TARGET_DIR"
