# GTA Official Experiment

This document describes the strict GTA-aligned formal experiment path.

## Goal

Use the official GTA tool deployment path instead of the local approximation layer:

- official `open-compass/GTA` repo
- official `agentlego/benchmark.py`
- official `agentlego/benchmark_toollist.txt`
- official `agentlego-server`
- strict same-tool evaluation with no generated tools

## Required Environment

You need a separate official environment that matches the GTA README as closely as possible.

Minimum expectations:

- `agentlego-server` available on `PATH`
- official GTA repo cloned locally
- GPU runtime available
- official tool server reachable
- `SERPER_API_KEY` set for `GoogleSearch`
- `MATHPIX_APP_ID` and `MATHPIX_APP_KEY` set for `MathOCR`

## Preflight Check

Run this before the formal experiment:

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export PYTHONPATH=.
export VISION_AGENT_GTA_OFFICIAL_REPO=/path/to/GTA
export VISION_AGENT_GTA_TOOL_SERVER=http://127.0.0.1:16181

python scripts/check_gta_official_setup.py \
  --mode server \
  --server-url "$VISION_AGENT_GTA_TOOL_SERVER" \
  --repo-root "$VISION_AGENT_GTA_OFFICIAL_REPO" \
  --require-keys
```

The script exits non-zero if the setup is not suitable for a formal official-tool run.

## Start Official Tool Server

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export VISION_AGENT_GTA_OFFICIAL_REPO=/path/to/GTA
export VISION_AGENT_GTA_DEVICE=cuda:0
export VISION_AGENT_GTA_TOOL_SERVER_PORT=16181

bash scripts/start_gta_official_tool_server.sh
```

This launches the exact GTA tool set listed in the official `benchmark_toollist.txt`.

## Run Formal Same-Tool Experiment

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export VISION_AGENT_GTA_OFFICIAL_REPO=/path/to/GTA
export VISION_AGENT_GTA_TOOL_SERVER=http://127.0.0.1:16181
export SERPER_API_KEY=...
export MATHPIX_APP_ID=...
export MATHPIX_APP_KEY=...

bash scripts/run_gta_official_formal.sh gta_official_formal_v1
```

This runs the strict official-tool setting group:

- `direct_vlm`
- `pure_react`
- `toolpool_prompt_baseline`
- `same_tool_preset_tools_only`
- `skill_only_train_adaptive`
- `skill_only_frozen_inference`

## Notes

- Formal runs should use `VISION_AGENT_GTA_TOOL_MODE=official_server`.
- Do not use `auto` or approximation fallback for the final reported result.
- The resulting `summary.json` records the GTA runtime mode, tool server, official repo path, device hint, and whether required keys were present.
