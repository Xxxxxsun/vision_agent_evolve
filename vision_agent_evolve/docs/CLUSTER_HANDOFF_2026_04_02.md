# Cluster Handoff 2026-04-02

This document captures the current code state and the latest experiment status before the cluster is released.

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

Main files touched during this phase:

- `evolution/roles.py`
- `evolution/subset_loop.py`
- `evolution/loop.py`
- `evolution/benchmark_adapters.py`
- `core/agent.py`
- `core/structured_data.py`
- `tools/builtin_tools.py`
- `tools/__main__.py`
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
