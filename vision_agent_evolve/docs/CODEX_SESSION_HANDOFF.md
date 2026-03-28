# Codex Session Handoff

This document summarizes the important technical context, design decisions, fixes, commands, pitfalls, and current status from the recent Codex collaboration on this repo.

The goal is that a new Codex session can read this file and continue work immediately.

## 1. Project Goal

The current focus is a **subset-level self-evolution loop** for vision benchmarks.

There are two broad modes:

1. **Single-example evolve**
   - Keep the original `EvolutionLoop`
   - Solve one example repeatedly
   - If the case is solved after learning, promote the resulting skill/tool

2. **Subset-level evolve**
   - Introduce `SubsetEvolutionLoop`
   - Maintain:
     - `active/` = current best accepted capability set
     - `candidate/<run_id>/` = temporary proposal under evaluation
   - Only accept a candidate if it **strictly improves the score on the full training subset**
   - Do not promote based on a single seed case

Core design principle:

- **generation is not learning**
- only **accepted candidate bundles** become the learned capability set

## 2. Main Architectural Changes Already Implemented

### 2.1 Subset-level evolution loop

Implemented:

- `SubsetEvolutionLoop`
- `SubsetEvaluator`
- `SubsetPlanner`
- active/candidate/snapshots workflow
- train-subset-level gating

Primary files:

- [evolution/subset_loop.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/subset_loop.py)
- [evolution/store.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/store.py)
- [evolution/structured_runner.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/structured_runner.py)
- [evolution/types.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/types.py)

Important behavior:

- baseline is evaluated on the whole train subset
- planner sees a digest, not the whole raw training set
- candidate bundle is staged
- smoke validation runs
- candidate is evaluated on the whole train subset
- accept iff `candidate.primary_score > baseline.primary_score`
- tie is reject

### 2.2 Benchmark adapters and normalization layer

Added adapters / registration points for:

- `chartqa`
- `vstar`
- `hrbench`
- `mathvista`
- `textvqa`

Primary files:

- [evolution/benchmark_adapters.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/benchmark_adapters.py)
- [core/structured_data.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/structured_data.py)

Added prepare scripts:

- [scripts/prepare_vstar.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/prepare_vstar.py)
- [scripts/prepare_hrbench.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/prepare_hrbench.py)
- [scripts/prepare_mathvista.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/prepare_mathvista.py)
- [scripts/prepare_textvqa.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/prepare_textvqa.py)

### 2.3 Tool preference for planner

Subset-level planner supports:

- `balanced`
- `prefer_tools`
- `require_tools`

This is wired through:

- [scripts/run_structured_experiment.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/run_structured_experiment.py)
- [evolution/subset_loop.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/subset_loop.py)
- [evolution/structured_runner.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/structured_runner.py)

## 3. Progress / UX Improvements Already Implemented

### 3.1 Subset training progress output

Subset-level training was originally too silent.

Now `SubsetEvaluator.evaluate()` and smoke/candidate stages print:

- single-line progress refresh
- elapsed time
- accumulated accuracy
- accumulated average score
- last case id
- phase-level summaries

This was implemented in:

- [evolution/subset_loop.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/subset_loop.py)

### 3.2 Direct-vs-agent debugging script

Added:

- [scripts/debug_direct_vs_agent.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/debug_direct_vs_agent.py)

Purpose:

- run `direct_vlm` and empty-active agent baseline on the same cases
- save:
  - direct prompt
  - agent system prompt
  - sanitized messages
  - per-step trace
  - answers and scores

This was used to debug `TextVQA`.

## 4. Important Bug Fixes Already Implemented

### 4.1 `used_tool` was misleading

Problem:

- tool use in pre-chain execution (`chain_trace`) was not counted
- `used_tool` remained `false` even when the capability chain actually invoked tools

Fix:

- merge `chain_trace` into `tool_names`
- compute `used_tool` from merged list

Files:

- [evolution/structured_runner.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/structured_runner.py)
- [evolution/subset_loop.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/subset_loop.py)

### 4.2 `eval_structured_frozen.py` did not rebuild `summary.json`

Problem:

- running frozen eval separately appended per-case rows
- but did not rebuild summary
- `summary.json` could misleadingly show `frozen_inference: 0`

Fix:

- `StructuredBenchmarkRunner.rebuild_summary()` added
- `scripts/eval_structured_frozen.py` now rebuilds summary after frozen eval

Files:

- [evolution/structured_runner.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/structured_runner.py)
- [scripts/eval_structured_frozen.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/eval_structured_frozen.py)

### 4.3 Large-image upload failures (`image_too_large`)

Observed on:

- `VStar`
- likely relevant to `HRBench` too

Problem:

- several code paths bypassed `VLMClient` and uploaded raw images as base64
- backend rejected unsupported / too-large images

Fix:

- unified image upload through `VLMClient.image_data_url()`
- downscale/compress oversized images automatically
- tightened threshold to reduce backend failures

Files:

- [core/vlm_client.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/vlm_client.py)
- [core/agent.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/agent.py)
- [evolution/roles.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/roles.py)
- [evolution/structured_runner.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/structured_runner.py)

### 4.4 `core/__init__.py` forced OpenAI imports for prepare scripts

Problem:

- data-prep scripts imported `core.structured_data`
- Python executed `core/__init__.py`
- old `__init__` forced import of `vlm_client`
- that required `openai`/`pydantic` even for pure normalization jobs

Fix:

- lazy import pattern in [core/__init__.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/__init__.py)

### 4.5 Base64 flood in prepare-script errors

Problem:

- when image fields were malformed, exceptions printed giant raw records
- records containing base64 image payloads flooded the terminal

Fix:

- summarized error reporting in [core/structured_data.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/structured_data.py)
- added `--limit` to all prepare scripts for debugging small batches

### 4.6 `HRBench` option extraction was wrong

Problem:

- raw HRBench options can be stored directly in columns `A/B/C/D`
- old normalizer only looked for `choices/options/...`
- direct baseline and scoring looked broken because choices were missing

Fix:

- `_extract_choices()` now supports `A/B/C/D` columns

Files:

- [core/structured_data.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/structured_data.py)

### 4.7 `HRBench` renormalization was too slow

Problem:

- repeated normalize jobs re-decoded and re-wrote huge cached images

Fix:

- `_save_image_bytes()` now reuses existing cached output PNGs when present

File:

- [core/structured_data.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/core/structured_data.py)

### 4.8 `MathVista` planner representative ids crashed subset loop

Observed error:

- planner returned representative ids like `case_id=11`
- `cases_by_id` contained `11`
- caused `KeyError: 'case_id=11'`

Fix:

- normalize representative ids before `materialize_bundle()`
- support forms like:
  - `case_id=11`
  - `case=11`
  - `id=11`
  - trailing summary fragments

File:

- [evolution/subset_loop.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/subset_loop.py)

## 5. Benchmark-Specific Notes

### 5.1 ChartQA

Status:

- fully wired and relatively stable
- existing normalized data lives in:
  - `datasets/structured_chartqa/chartqa/train.jsonl`
  - `datasets/structured_chartqa/chartqa/val.jsonl`

Known counts in local repo:

- train: `28299`
- val: `1920`

Important insight:

- subset-level evolve works well here
- direct and agent are both meaningful baselines

### 5.2 VStar

Status:

- prepare script exists
- subset-level evolve and direct baseline commands exist
- image compression fix was important here because oversized uploads caused failures

### 5.3 HRBench4K

Status:

- prepare script exists and works
- normalized split convention:
  - `train=100`
  - `val=700`

Important learned artifact:

- `learned/hrbench4k_train100_v1` exists locally in workspace

Observed issue with learned capability:

- the original evolved `hrbench_single` skill and `color_recognition_tool` were too narrow
- they overfit a very specific “yellow shirt + backpack color” pattern

Manual improvement already added locally:

- new tool:
  - [learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.py)
- new metadata:
  - [learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.json](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.json)
- updated skill:
  - [learned/hrbench4k_train100_v1/active/skills/hrbench_single/SKILL.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/learned/hrbench4k_train100_v1/active/skills/hrbench_single/SKILL.md)

Intent of new manual tool:

- generate labeled focus grid
- original + center crop + four quadrants + sharpened center
- help with text / direction / color / small local evidence questions

### 5.4 TextVQA

Status:

- prepare script exists
- benchmark support exists
- direct baseline works
- subset evolve path is currently problematic

Important insight from debugging:

- `TextVQA` is strong under `direct_vlm`
- empty-active agent baseline can be much worse
- not because the model cannot see the answer
- because the ReAct protocol hurts it:
  - first turn often becomes a format error
  - second turn returns a verbose sentence instead of the shortest answer span

This was verified with:

- [scripts/debug_direct_vs_agent.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/debug_direct_vs_agent.py)

Local prompt-only improvement already added:

- in [evolution/loop.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/loop.py)
- `TextVQA` / `textvqa_ocr` cases now receive task-specific instructions:
  - direct short answer preferred
  - avoid bash unless necessary
  - `Final Answer` must be shortest exact answer string
  - no explanation, no full sentences when not needed

Practical interpretation:

- `TextVQA` is a weak benchmark for tool-heavy evolve in the current framework
- it is still useful:
  - as a direct baseline benchmark
  - as a place to evolve short-answer discipline / OCR extraction skills

### 5.5 MathVista

Status:

- support exists
- normalization uses `testmini`
- free-form scoring now has LLM-judge fallback

Important raw-data caveat:

- raw MathVista directory includes `images.zip`
- images must be extracted before normalization
- earlier failures happened because records referenced `images/1.jpg` etc. but files were still inside the zip

Important current scoring behavior:

- multiple-choice: deterministic
- free-form:
  - deterministic rules first
  - then LLM judge fallback if rules fail

Files:

- [evolution/benchmark_adapters.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/evolution/benchmark_adapters.py)

## 6. Current Commands / Operational Guide

The current canonical command collection lives in:

- [docs/STRUCTURED_BENCHMARK_COMMANDS.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/docs/STRUCTURED_BENCHMARK_COMMANDS.md)

Use that file for:

- prepare commands
- evolve commands
- frozen eval commands
- direct VLM commands
- debug commands

## 7. Notable Experimental Findings from This Work

### 7.1 Empty-active agent baseline is not the same as direct VLM

This caused repeated confusion and is important.

- `active = empty` only means no learned skill/tool
- it does **not** mean direct VLM baseline

The empty-active agent still uses:

- the ReAct system prompt
- action/observation protocol
- parser constraints
- completion formatting rules

This difference is especially important on `TextVQA`.

### 7.2 Candidate generation vs accepted learning

Another important conceptual point:

- generating a skill/tool does not mean the system learned it
- only an **accepted** candidate enters `active`

This mattered in early ChartQA debugging when `candidate/` contained skills but `active/` remained empty.

### 7.3 `used_tool` and `summary.json` used to be misleading

When analyzing older artifacts, remember:

- old runs may have stale `summary.json`
- old runs may undercount tool usage if tools were used in pre-chain execution

Use:

- rebuilt summaries
- `per_case.jsonl`
- `chain_trace`

to interpret older runs carefully.

## 8. Files Added During This Work

Important additions:

- [scripts/debug_direct_vs_agent.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/debug_direct_vs_agent.py)
- [scripts/run_multibench_full.sh](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/scripts/run_multibench_full.sh)
- [docs/STRUCTURED_BENCHMARK_COMMANDS.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/docs/STRUCTURED_BENCHMARK_COMMANDS.md)
- [docs/CODEX_SESSION_HANDOFF.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/docs/CODEX_SESSION_HANDOFF.md)

Additional manually created benchmark-specific learned artifacts:

- [learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.py](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.py)
- [learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.json](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/learned/hrbench4k_train100_v1/active/tools/hrbench_focus_grid_tool.json)

## 9. Suggested Next Steps for a New Codex Session

Recommended order:

1. Read:
   - this file
   - [docs/STRUCTURED_BENCHMARK_COMMANDS.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/docs/STRUCTURED_BENCHMARK_COMMANDS.md)

2. Decide which active benchmark to continue:
   - `ChartQA`
   - `HRBench`
   - `VStar`
   - `MathVista`
   - `TextVQA`

3. If continuing `TextVQA`:
   - run `scripts/debug_direct_vs_agent.py`
   - verify whether prompt-only fix narrowed the gap

4. If continuing `MathVista`:
   - confirm `images.zip` is extracted on the server
   - use a fresh `subset-id`

5. If continuing `HRBench`:
   - consider evaluating whether `hrbench_focus_grid_tool` helps more than the narrow color tool

6. If doing paper-writing / result aggregation:
   - also inspect [PAPER_PLAN.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/PAPER_PLAN.md)

## 10. Important Repo-State Notes

At the time this handoff was written:

- repo has untracked/new:
  - [docs/STRUCTURED_BENCHMARK_COMMANDS.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/docs/STRUCTURED_BENCHMARK_COMMANDS.md)
  - [docs/CODEX_SESSION_HANDOFF.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/docs/CODEX_SESSION_HANDOFF.md)
  - [PAPER_PLAN.md](/Users/macbook/Desktop/exp_ali/Glue_SWE/vision_agent_evolve/PAPER_PLAN.md) is present locally

Parent directories also show modifications (`../Glue`, `../Glue_SWE`, `../react-agent-minimal`) but they are outside this repo’s working focus and should not be reverted from here.
