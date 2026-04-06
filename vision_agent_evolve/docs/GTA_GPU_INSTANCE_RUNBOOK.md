# GTA GPU Instance Runbook

This document is the practical runbook for moving the GTA formal experiment to
another instance that has GPU resources.

Use this runbook when the goal is:

- strict GTA same-tool evaluation
- official `agentlego-server`
- no approximation fallback in final results
- reproducible experiment output that can be copied back into this repo

## 1. Machine Expectations

Recommended:

- 2 GPUs
  - GPU 0: VLM service
  - GPU 1: official GTA tool server
- 1 GPU is acceptable if the experiment is run serially
- 24 GB or more VRAM is the safest target for the official tool stack
- enough disk for:
  - this repo
  - official `open-compass/GTA`
  - model weights
  - experiment artifacts

## 2. Clone Repos

```bash
cd ~
git clone git@github.com:Xxxxxsun/vision_agent_evolve.git
git clone https://github.com/open-compass/GTA.git
```

Repo layout assumed below:

```text
~/vision_agent_evolve/vision_agent_evolve
~/GTA
```

## 3. Prepare Dataset

The formal run expects the GTA dataset under the same location used by this repo:

```text
/root/vision_agent_evolve/datasets/GTA/opencompass/data/gta_dataset
```

If the new instance uses a different root, either:

- copy the dataset into the same path, or
- adjust the command arguments in the run script when launching the experiment

## 4. Create Official Tool Environment

This should be separate from the lightweight repo environment.

```bash
conda create -n agentlego python=3.11.9 -y
conda activate agentlego

cd ~/GTA/agentlego
pip install -r requirements_all.txt
pip install agentlego
pip install -e .
mim install mmengine
mim install mmcv==2.1.0
```

Official GTA notes also require:

- `transformers==4.40.1`
- the `_supports_sdpa` compatibility edit mentioned in the GTA README

## 5. Prepare Model Service

The GTA tool server and the experiment runner both need a model endpoint for the
agent itself. Keep this separate from the tool server.

Example with LMDeploy:

```bash
lmdeploy serve api_server /path/to/your/model \
  --server-port 12580 \
  --model-name your_model_name
```

Then export:

```bash
export VLM_BASE_URL="http://127.0.0.1:12580/v1"
export VLM_API_KEY="EMPTY"
export VLM_MODEL="your_model_name"
```

## 6. Export Official GTA Variables

In the shell used for the formal run:

```bash
export VISION_AGENT_GTA_OFFICIAL_REPO=~/GTA
export VISION_AGENT_GTA_DEVICE=cuda:1
export VISION_AGENT_GTA_TOOL_SERVER_PORT=16181
export VISION_AGENT_GTA_TOOL_SERVER=http://127.0.0.1:16181
export VISION_AGENT_GTA_TOOL_MODE=official_server

export SERPER_API_KEY=...
export MATHPIX_APP_ID=...
export MATHPIX_APP_KEY=...
```

If only one GPU is available, set `VISION_AGENT_GTA_DEVICE=cuda:0` and run the
VLM service plus tool server on the same card.

## 7. Start Official GTA Tool Server

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
conda activate agentlego
bash scripts/start_gta_official_tool_server.sh
```

This launches the exact official GTA tool list from:

- `~/GTA/agentlego/benchmark.py`
- `~/GTA/agentlego/benchmark_toollist.txt`

## 8. Preflight Check

Before the real run, verify the setup from this repo:

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export PYTHONPATH=.

python scripts/check_gta_official_setup.py \
  --mode server \
  --server-url "$VISION_AGENT_GTA_TOOL_SERVER" \
  --repo-root "$VISION_AGENT_GTA_OFFICIAL_REPO" \
  --require-keys
```

The expected result is:

- `"ok": true`
- no missing required tools
- no key failures
- no GPU/runtime failure

Do not start the formal experiment if this check fails.

## 9. Launch the Formal Experiment

```bash
cd ~/vision_agent_evolve/vision_agent_evolve
export PYTHONPATH=.

bash scripts/run_gta_official_formal.sh gta_official_formal_v1
```

Default setting group:

- `direct_vlm`
- `pure_react`
- `toolpool_prompt_baseline`
- `same_tool_preset_tools_only`
- `skill_only_train_adaptive`
- `skill_only_frozen_inference`

The formal run is configured to:

- use official tool server mode
- use the official GTA 14-tool pool
- disable generated tools
- keep same-tool constraints during evolution

## 10. Output Locations

Primary outputs will be under:

```text
artifacts/structured_benchmarks/gta_official_formal_v1/
```

Most important files:

- `summary.json`
- `per_case.jsonl`
- `train_subset_manifest.json`

The `summary.json` records:

- GTA tool mode
- tool server URL
- official repo path
- GTA device hint
- whether Serper / Mathpix keys were present

## 11. Copy Results Back

Copy at least the following back from the GPU instance:

```text
artifacts/structured_benchmarks/gta_official_formal_v1/
```

If you want the full capability snapshot as well, also copy:

```text
learned/gta_official_formal_v1/
```

## 12. Recommended Session Split

Recommended if 2 GPUs are available:

- Terminal 1:
  - `CUDA_VISIBLE_DEVICES=0`
  - start model service
- Terminal 2:
  - `CUDA_VISIBLE_DEVICES=1`
  - start `agentlego-server`
- Terminal 3:
  - run preflight and formal experiment from this repo

If only 1 GPU is available:

- start model service first
- start tool server second
- monitor VRAM closely
- expect slower runs and higher OOM risk

## 13. Failure Policy

Treat the run as non-formal if any of the following happens:

- `VISION_AGENT_GTA_TOOL_MODE` is not `official_server`
- preflight check fails
- server is missing one of the 14 official GTA tools
- `SERPER_API_KEY` is missing
- `MATHPIX_APP_ID` or `MATHPIX_APP_KEY` is missing
- the experiment falls back to approximation mode

If any of those occurs, stop and fix the environment before using the results.
