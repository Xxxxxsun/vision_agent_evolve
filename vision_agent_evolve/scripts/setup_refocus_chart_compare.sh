#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_ROOT="${RAW_ROOT:-/root/vqa_datasets/datasets/refocus_chart_hf}"
NORMALIZED_ROOT="${NORMALIZED_ROOT:-${PROJECT_ROOT}/datasets/structured_vtoolr1_compare}"
VTOOL_ROOT="${VTOOL_ROOT:-/root/VTool-R1}"

echo "[setup] project root: ${PROJECT_ROOT}"
echo "[setup] raw root: ${RAW_ROOT}"
echo "[setup] normalized root: ${NORMALIZED_ROOT}"
echo "[setup] vtool root: ${VTOOL_ROOT}"

if [ ! -d "${VTOOL_ROOT}/.git" ]; then
  git clone https://github.com/VTOOL-R1/VTool-R1.git "${VTOOL_ROOT}"
else
  git -C "${VTOOL_ROOT}" pull --ff-only
fi

python "${PROJECT_ROOT}/scripts/download_refocus_chart.py" \
  --local-dir "${RAW_ROOT}"

python "${PROJECT_ROOT}/scripts/prepare_refocus_chart.py" \
  --raw-data-root "${RAW_ROOT}" \
  --normalized-data-root "${NORMALIZED_ROOT}"

python - <<'PY'
from pathlib import Path
import json

root = Path("/root/VTool-R1/results")
root.mkdir(parents=True, exist_ok=True)
payload = {
    "accuracy": 0.807,
    "reported_percent": 80.7,
    "model": "Qwen2.5-VL-7B",
    "benchmark": "Refocus_Chart / Chart Split",
    "source": "VTool-R1 paper Table 1 (ICLR 2026)",
    "notes": "Published chart split result for VTool-R1-7B. The paper also reports direct=76.2 and prompted tool use=53.4 on the same split."
}
out = root / "refocus_chart_vtool_r1_reported.json"
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[setup] wrote {out}")
PY

echo "[done] Refocus_Chart compare assets are ready."
