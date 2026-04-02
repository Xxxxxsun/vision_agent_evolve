# Cluster Handoff 2026-04-02

This document captures the current code state and the latest experiment status before the cluster is released.

Current git branch at capture time:

- `main`

## Current Repo Update Check

Before this handoff refresh, the worktree was checked again.

What is already in good shape:

- The third-stage mastery refactor is already committed.
- Progressive-disclosure skills (`SKILL.md + references/*.md`) are already committed.
- `preset_tools_only`, frozen-eval resume, and train checkpointing are already committed.
- GTA adapter and preset-tool runtime support are already committed.

What does **not** need to be pushed as code:

- In-progress or partial experiment artifacts under `artifacts/` and `learned/`
- Runtime logs under `logs/`
- Scratch analysis scripts such as `measure*.py`, `find_*.py`, `check_*.py`
- Ad hoc files such as `solution.py`, `solution.sh`, `final_answer.txt`

So the only new update in this refresh is documentation: an explicit environment section and a clearer note about what should and should not be treated as committed source state.

## Environment Requirements

### Python

- Python `>=3.10`

### Core install

From repo root:

```bash
cd /root/vision_agent_evolve/vision_agent_evolve
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional dev install:

```bash
pip install -e ".[dev]"
```

### Python dependencies

Declared in `pyproject.toml`:

- `openai>=1.0.0`
- `opencv-python>=4.8.0`
- `numpy>=1.24.0,<2`
- `Pillow>=10.0.0`

Optional dev dependencies:

- `pytest>=7.0.0`
- `black>=23.0.0`
- `ruff>=0.1.0`

### Runtime environment variables

The cluster runs in this handoff mainly used the Alibaba-compatible endpoint.

Typical setup:

```bash
export PYTHONPATH=.
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_MODEL="gpt-5.4-0305-global"
export VLM_USER_ID="345245"
export VLM_ACCESS_KEY="efc8c9ca4ac5b0dd4018bcd3a83d767d"
export VLM_QUOTA_ID="79b2a6c6-f7c6-4138-aae0-abaa3b1608e5"
export VLM_APP="llm_application"
export VLM_API_KEY="dummy"
```

Notes:

- `VLM_API_KEY` can be a dummy value for the Alibaba path used here.
- `qwen3.5-plus`, `doubao-seed-2.0-pro`, and `gpt-5.4-0305-global` all ran on this path by changing only `VLM_MODEL`.
- `gemini-3.1-pro-preview` uses the Gemini-over-Alibaba adapter now implemented in `core/vlm_client.py`.

### Dataset roots used in this cluster

Structured normalized datasets live under:

- `datasets/structured_multibench/`

Important raw-data roots used in this cluster:

- VStar:
  - `/root/vqa_datasets/datasets/vstar_bench`
- HRBench:
  - `/root/vqa_datasets/datasets/hr_bench`
- MathVista:
  - `/root/vqa_datasets/datasets/mathvista`
- ChartQA:
  - `/root/vqa_datasets/datasets/chartqa`
- GTA raw root:
  - `/root/vision_agent_evolve/datasets/GTA/opencompass/data/gta_dataset`

## What Changed

This round focused on restructuring the third stage of evolution from a flat skill rewrite into a `tool mastery` stage.

Key code changes:

- `preset tools + skill-only` path was introduced earlier and remains the base runtime for these experiments.
- Third-stage mastery was refactored to learn tool usage boundaries instead of only regenerating a short SOP.
- Progressive-disclosure skill packages are now supported:
  - top-level `SKILL.md` acts as a router
  - sibling `references/*.md` files hold branch details
- Skill loading/rendering was updated so only explicitly referenced branch docs are expanded.
- Capability store now writes full skill packages, not just a single `SKILL.md`.
- A `preset_tools_only` evaluation setting was added so full experiments can compare:
  - `agent_train_adaptive`
  - `preset_tools_only`
  - `frozen_inference`
- Frozen-eval resume was improved:
  - healthy records are skipped
  - timeout / empty-answer records are rerun
- Agent-train checkpointing was added so long subset runs write partial train records instead of losing everything on interruption.
- GTA benchmark normalization and runtime adaptation were added so GTA can run through the current structured benchmark pipeline.
- GTA-native preset tools were added under the exact dataset names:
  - `OCR`
  - `ImageDescription`
  - `Calculator`
  - `GoogleSearch`
  - `CountGivenObject`
  - `MathOCR`
  - `TextToBbox`
  - `RegionAttributeDescription`
  - `Solver`
  - `Plot`
  - `DrawBox`
  - `AddText`
  - `TextToImage`
  - `ImageStylization`
- Tool CLI dispatch now supports GTA-style `key=value` arguments instead of only `<image_path>`.
- Agent prompting and mastery-skill templating were updated so GTA skills emit runnable commands like:
  - `python -m tools OCR image=<image_path>`
  - `python -m tools Calculator expression="..."`
  - `python -m tools GoogleSearch query="..." k=4`

Main files touched during this phase:

- `evolution/roles.py`
- `evolution/subset_loop.py`
- `evolution/loop.py`
- `evolution/benchmark_adapters.py`
- `core/agent.py`
- `core/structured_data.py`
- `tools/builtin_tools.py`
- `tools/__main__.py`
- `tools/gta_tools.py`
- `tools/implementations/shared/gta_utils.py`
- `tools/preset_types.py`
- `scripts/prepare_gta.py`
- `test_structured_benchmark.py`
- `test_minimal_evolve_loop.py`

## Progressive-Disclosure Skill Format

The intended third-stage output is now:

- `skills/<family>/SKILL.md`
- `skills/<family>/references/*.md`

Example active skills already using this layout:

- `learned/mathvista_train100_gpt54_masterypkg_v1/active/skills/mathvista_generic_free_form/`
- `learned/hrbench4k_train100_gpt54_masterypkg_v1/active/skills/hrbench_cross/`
- `learned/chartvqa_train25_gpt54_masterypkg_v1/active/skills/chartqa/`

## Full Mastery Experiments

Formal runs launched with the current mastery architecture:

- Models:
  - `gpt-5.4-0305-global`
  - `qwen3.5-plus`
  - `doubao-seed-2.0-pro`
  - `gemini-3.1-pro-preview`
- Benchmarks:
  - `vstar`
  - `hrbench4k`
  - `mathvista`
  - `chartvqa`
- Settings:
  - `agent_train_adaptive`
  - `preset_tools_only`
  - `frozen_inference`

Train / eval sizes:

- `vstar`: train `40`, val `151`
- `hrbench4k`: train `100`, val `700`
- `mathvista`: train `100`, val `900`
- `chartvqa`: train `25`, val `1920`

## Completed Results

These runs already have full three-way results written into `summary.json`.

| Model | Benchmark | agent_train_adaptive | preset_tools_only | frozen_inference |
| --- | --- | ---: | ---: | ---: |
| gpt-5.4 | vstar | 0.6750 | 0.6623 | 0.6093 |
| gpt-5.4 | hrbench4k | 0.6000 | 0.6243 | 0.6171 |
| gpt-5.4 | mathvista | 0.6400 | 0.6089 | 0.6156 |
| gpt-5.4 | chartvqa | 0.6000 | 0.7786 | 0.6594 |
| qwen3.5-plus | vstar | 0.9000 | 0.7748 | 0.7947 |
| doubao-seed-2.0-pro | vstar | 0.9500 | 0.8675 | 0.8609 |
| doubao-seed-2.0-pro | hrbench4k | 0.8400 | 0.8700 | 0.8571 |
| doubao-seed-2.0-pro | mathvista | 0.7900 | 0.8756 | 0.8467 |
| gemini-3.1-pro-preview | vstar | 0.9000 | 0.7682 | 0.8344 |

Quick takeaways from completed runs:

- `mathvista / gpt-5.4` is one of the few completed cases where `frozen_inference > preset_tools_only`.
- `chartvqa / gpt-5.4` strongly favors `preset_tools_only`.
- `vstar` remains strong for `qwen`, `doubao`, and `gemini`, but `frozen_inference` is not always above `preset_tools_only`.

## GTA Status

### Code / Data State

GTA is now wired into the current repo flow instead of the old benchmark-specific branch flow.

Important paths:

- Raw GTA root used in this session:
  - `/root/vision_agent_evolve/datasets/GTA/opencompass/data/gta_dataset`
- Normalized GTA dataset:
  - `datasets/structured_multibench/gta/train.jsonl`
  - `datasets/structured_multibench/gta/val.jsonl`
  - `datasets/structured_multibench/gta/manifest.json`
- GTA preset-tool implementation:
  - `tools/gta_tools.py`
  - `tools/implementations/shared/gta_utils.py`
- GTA CLI / agent / mastery wiring:
  - `tools/__main__.py`
  - `tools/builtin_tools.py`
  - `evolution/loop.py`
  - `evolution/subset_loop.py`
  - `core/agent.py`

### GTA Results Already Finished

1. Direct GPT-5.4 baseline on val

- Subset id:
  - `gta_direct_gpt54_val_full_v1`
- Summary:
  - `artifacts/structured_benchmarks/gta_direct_gpt54_val_full_v1/summary.json`
- Result:
  - `77 / 121 = 0.6364`

2. Pre-adaptation `agent_train_adaptive + frozen_inference`

- Subset id:
  - `gta_train51_gpt54_v1`
- Summary:
  - `artifacts/structured_benchmarks/gta_train51_gpt54_v1/summary.json`
- Result:
  - train final `31 / 51 = 0.6078`
  - frozen val `77 / 121 = 0.6364`
- Interpretation:
  - no accepted round
  - frozen accuracy matched the direct baseline
  - this was the evidence that GTA needed real runtime tool adaptation rather than only prompt-level tool names

### GTA Verification After Adaptation

Focused checks completed successfully:

- `python -m py_compile` passed for the GTA tool wiring files
- `python -m tools Calculator 'expression=round(75 / 59 * 100)'` returned `127`
- `python -m tools DrawBox image=/tmp/gta_tool_smoke.png 'bbox=(4,4,20,20)' annotation=target` returned `STATUS: ok`
- Tests passed:
  - `env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -q test_structured_benchmark.py -k 'execute_gta_calculator_builtin_tool or execute_gta_draw_box_builtin_tool or evolution_loop_tool_snapshot_includes_builtin_tools or gta_agent_prompt_includes_gta_tool_hints or skill_from_mastery_strategy'`
  - `6 passed`
  - `env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=. python -m pytest -q test_minimal_evolve_loop.py -k 'builtin_tools_catalog_is_nonempty or execute_builtin_tool_writes_artifact'`
  - `2 passed`

### GTA Re-Run Started But Not Finished

A new run was started after the GTA tool adaptation:

- Subset id:
  - `gta_preset_tools_gpt54_v1`
- Intended settings:
  - `preset_tools_only`
  - `agent_train_adaptive`
  - `frozen_inference`
- Current summary path:
  - `artifacts/structured_benchmarks/gta_preset_tools_gpt54_v1/summary.json`

Important note:

- The current `summary.json` for `gta_preset_tools_gpt54_v1` is not a final result.
- It was written during an in-progress run and still shows zeros.
- During the live rerun, progress output showed the adapted baseline beginning with correct cases (`gta_0`, `gta_102`, `gta_123`, `gta_134`, `gta_137`, `gta_138`, `gta_16`), which is already a different trajectory from the earlier failed GTA setup.
- Treat `gta_preset_tools_gpt54_v1/summary.json` as partial / stale unless the run is resumed to completion and summary is rebuilt.

### GTA Resume Command

If this needs to be resumed on another machine with the same Alibaba endpoint setup, use:

```bash
cd /root/vision_agent_evolve/vision_agent_evolve
export PYTHONPATH=.
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_MODEL="gpt-5.4-0305-global"
export VLM_USER_ID="345245"
export VLM_ACCESS_KEY="efc8c9ca4ac5b0dd4018bcd3a83d767d"
export VLM_QUOTA_ID="79b2a6c6-f7c6-4138-aae0-abaa3b1608e5"
export VLM_APP="llm_application"

python scripts/run_structured_experiment.py \
  --dataset gta \
  --raw-data-root /root/vision_agent_evolve/datasets/GTA/opencompass/data/gta_dataset \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id gta_preset_tools_gpt54_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 51 \
  --held-out-limit 121 \
  --max-planning-rounds 3 \
  --representatives-per-cluster 2 \
  --families-per-round-limit 2 \
  --tool-preference prefer_tools \
  --settings preset_tools_only agent_train_adaptive frozen_inference
```

If only the post-adaptation baseline comparison is needed quickly, prioritize:

1. `preset_tools_only`
2. `frozen_inference`

before spending another full round budget on more evolution.

## In-Progress Runs At Capture Time

These runs were still active when this handoff was written.

| Model | Benchmark | Current train summary |
| --- | --- | ---: |
| qwen3.5-plus | hrbench4k | 0.8300 |
| qwen3.5-plus | mathvista | 0.7500 |
| qwen3.5-plus | chartvqa | 0.6400 |
| doubao-seed-2.0-pro | chartvqa | 0.6400 |
| gemini-3.1-pro-preview | hrbench4k | 0.8200 |
| gemini-3.1-pro-preview | mathvista | 0.8500 |
| gemini-3.1-pro-preview | chartvqa | 0.6800 |

Operational notes:

- `qwen3.5-plus` is the slowest family but was still progressing.
- `gemini-3.1-pro-preview` showed repeated transient read timeouts, but recovery logic was working and the jobs were still moving.
- `doubao-seed-2.0-pro` was generally healthy and comparatively stable.

## Important Paths

Primary outputs:

- Full summaries:
  - `artifacts/structured_benchmarks/<subset_id>/summary.json`
- Per-case records:
  - `artifacts/structured_benchmarks/<subset_id>/per_case.jsonl`
- Logs:
  - `logs/<subset_id>.log`
- Learned capabilities:
  - `learned/<subset_id>/active/skills/...`
  - `learned/<subset_id>/active/training_memory/training_digest.json`

Representative completed mastery runs:

- `vstar_train40_gpt54_masterypkg_v1`
- `hrbench4k_train100_gpt54_masterypkg_v1`
- `mathvista_train100_gpt54_masterypkg_v1`
- `chartvqa_train25_gpt54_masterypkg_v1`
- `vstar_train40_qwen35_masterypkg_v1`
- `vstar_train40_doubao_seed20_masterypkg_v1`
- `hrbench4k_train100_doubao_seed20_masterypkg_v1`
- `mathvista_train100_doubao_seed20_masterypkg_v1`
- `vstar_train40_gemini31_masterypkg_v1`

## Recommended Next Step

When resuming on another machine:

1. Inspect the in-progress `summary.json` and `logs/*.log` first.
2. Prioritize collecting the remaining final results for:
   - `qwen3.5-plus / hrbench4k, mathvista, chartvqa`
   - `doubao-seed-2.0-pro / chartvqa`
   - `gemini-3.1-pro-preview / hrbench4k, mathvista, chartvqa`
3. Once all full runs are complete, compare:
   - `preset_tools_only`
   - `frozen_inference`
4. Then review active skill packages to identify when the mastery router truly improves over tool-only.
5. For GTA specifically:
   - ignore the stale zero-valued `gta_preset_tools_gpt54_v1/summary.json`
   - resume the adapted GTA run
   - compare:
     - `gta_direct_gpt54_val_full_v1`
     - `gta_train51_gpt54_v1`
     - resumed `gta_preset_tools_gpt54_v1`
