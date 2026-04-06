#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${VISION_AGENT_GTA_OFFICIAL_REPO:-/tmp/GTA_official}"
PORT="${VISION_AGENT_GTA_TOOL_SERVER_PORT:-16181}"
DEVICE="${VISION_AGENT_GTA_DEVICE:-cuda:0}"

if [[ ! -f "${REPO_ROOT}/agentlego/benchmark.py" ]]; then
  echo "Missing official GTA benchmark.py under ${REPO_ROOT}/agentlego" >&2
  exit 1
fi

if [[ ! -f "${REPO_ROOT}/agentlego/benchmark_toollist.txt" ]]; then
  echo "Missing benchmark_toollist.txt under ${REPO_ROOT}/agentlego" >&2
  exit 1
fi

if ! command -v agentlego-server >/dev/null 2>&1; then
  echo "agentlego-server is not installed or not on PATH" >&2
  exit 1
fi

cd "${REPO_ROOT}/agentlego"
echo "Starting GTA official tool server from ${REPO_ROOT}/agentlego on port ${PORT} using device ${DEVICE}"
agentlego-server start \
  --port "${PORT}" \
  --device "${DEVICE}" \
  --extra ./benchmark.py \
  $(cat benchmark_toollist.txt) \
  --host 0.0.0.0
