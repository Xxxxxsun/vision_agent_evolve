#!/usr/bin/env bash
set -euo pipefail

VTOOL_ROOT="${VTOOL_ROOT:-/root/VTool-R1}"
MODEL_ROOT="${MODEL_ROOT:-/root/models}"
DATA_ROOT="${DATA_ROOT:-/root/vqa_datasets}"

echo "[bootstrap] VTool-R1 root: ${VTOOL_ROOT}"
echo "[bootstrap] Model root: ${MODEL_ROOT}"
echo "[bootstrap] Data root: ${DATA_ROOT}"

mkdir -p "${MODEL_ROOT}" "${DATA_ROOT}"

if [ ! -d "${VTOOL_ROOT}/.git" ]; then
  git clone https://github.com/VTOOL-R1/VTool-R1.git "${VTOOL_ROOT}"
else
  git -C "${VTOOL_ROOT}" pull --ff-only
fi

echo
echo "[next] Install VTool-R1 dependencies inside ${VTOOL_ROOT}"
echo "  cd ${VTOOL_ROOT}"
echo "  pip install -r requirements.txt"
echo
echo "[next] Download Qwen2.5-VL-7B and the released VTool-R1 checkpoint into ${MODEL_ROOT}"
echo "  huggingface-cli download Qwen/Qwen2.5-VL-7B-Instruct --local-dir ${MODEL_ROOT}/Qwen2.5-VL-7B-Instruct"
echo "  # Download the exact VTool-R1 checkpoint/model release documented by the official repo."
echo
echo "[next] Download benchmark data into ${DATA_ROOT}"
echo "  - ChartQA official data"
echo "  - ReFOCUS-Chart (HF: VTOOL/Refocus_Chart)"
echo "  - ReFOCUS/TableVQA official data"
echo
echo "[next] Then prepare local normalized data with:"
echo "  python scripts/prepare_chartqa.py --raw-data-root <chartqa_raw_root> --normalized-data-root ./datasets/structured_vtoolr1_compare"
echo "  python scripts/download_refocus_chart.py --local-dir ${DATA_ROOT}/datasets/refocus_chart_hf"
echo "  python scripts/prepare_refocus_chart.py --raw-data-root ${DATA_ROOT}/datasets/refocus_chart_hf --normalized-data-root ./datasets/structured_vtoolr1_compare"
echo "  python scripts/prepare_refocus_tablevqa.py --raw-data-root <refocus_raw_root> --normalized-data-root ./datasets/structured_vtoolr1_compare"
