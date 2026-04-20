# VTool-R1 API Comparison Workflow

This workflow is for the no-GPU setting:

- use this repo's self-evolution framework
- call a VLM through the existing Alibaba/OpenAI-compatible proxy path
- keep the `VTool-R1` tool protocol fixed
- disable new tool generation
- compare against `VTool-R1` as a reported reference

It is not a same-backbone reproduction of `VTool-R1`. It is a strict same-benchmark, same-tool-pool, training-free API evaluation line.

## Refocus_Chart same-benchmark line

`VTool-R1` reports a unified `Chart Split` result in Table 1 of the ICLR 2026 paper. The open `VTOOL/Refocus_Chart` dataset on Hugging Face is the released chart benchmark variant with:

- `train`: 14,344 rows
- `test`: 826 rows

For the `Qwen2.5-VL-7B` row, the paper reports:

- direct / pure inference: `76.2`
- prompted tool use baseline: `53.4`
- `VTool-R1-7B`: `80.7`

Source: VTool-R1 paper Table 1, chart split (`ICLR 2026`).

## 1. Configure the API client

This repo already supports Alibaba chat and OpenAI-compatible APIs through `core/vlm_client.py`.

Example Alibaba proxy env:

```bash
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_API_KEY="YOUR_PROXY_TOKEN"
export VLM_MODEL="YOUR_VISION_MODEL"
export VLM_USER_ID="YOUR_USER_ID"
export VLM_ACCESS_KEY="YOUR_ACCESS_KEY"
export VLM_QUOTA_ID="YOUR_QUOTA_ID"
```

Only non-secret config is written into `summary.json`:

- `vlm_base_url`
- `vlm_model`
- `vlm_api_style`
- whether Alibaba mode was used

## 2. Prepare datasets

Bootstrap the external assets once:

```bash
bash scripts/bootstrap_vtool_r1_assets.sh
```

Normalize ChartQA:

```bash
python scripts/prepare_chartqa.py \
  --raw-data-root /root/VTool-R1/ChartQA/ChartQA\ Dataset \
  --normalized-data-root ./datasets/structured_vtoolr1_compare
```

Normalize ReFOCUS-TableVQA:

```bash
python scripts/prepare_refocus_tablevqa.py \
  --raw-data-root /root/vqa_datasets/datasets/refocus_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare
```

Download and normalize ReFOCUS-Chart:

```bash
python scripts/download_refocus_chart.py \
  --local-dir /root/vqa_datasets/datasets/refocus_chart_hf

python scripts/prepare_refocus_chart.py \
  --raw-data-root /root/vqa_datasets/datasets/refocus_chart_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare
```

## 3. Run the fixed-tool-pool baselines

Use the VTool-R1 bbox tools that are wrapped in `tools/builtin_tools.py`.

Example chart tool pool:

```bash
CHART_TOOLS="focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw"
```

In `bash`, pass the tool names as plain positional arguments. Do not use `${=CHART_TOOLS}`, which is `zsh` syntax.

Example table tool pool:

```bash
TABLE_TOOLS="focus_on_columns_with_mask focus_on_rows_with_mask focus_on_columns_with_draw focus_on_rows_with_draw"
```

ChartQA:

```bash
python scripts/run_structured_experiment.py \
  --dataset chartqa \
  --raw-data-root /root/VTool-R1/ChartQA/ChartQA\ Dataset \
  --normalized-data-root ./datasets/structured_vtoolr1_compare \
  --subset-id vtoolr1_chartqa_api_same_tools_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 200 \
  --held-out-limit 500 \
  --fixed-tool-names focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

ReFOCUS-Chart:

```bash
python scripts/run_structured_experiment.py \
  --dataset refocus_chart \
  --raw-data-root /root/vqa_datasets/datasets/refocus_chart_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare \
  --subset-id vtoolr1_refocus_chart_api_same_tools_v1 \
  --evolve-split train \
  --held-out-split test \
  --train-subset-size 200 \
  --held-out-limit 826 \
  --fixed-tool-names focus_on_x_values_with_mask focus_on_y_values_with_mask focus_on_x_values_with_draw focus_on_y_values_with_draw \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

ReFOCUS-TableVQA:

```bash
python scripts/run_structured_experiment.py \
  --dataset refocus_tablevqa \
  --raw-data-root /root/vqa_datasets/datasets/refocus_hf \
  --normalized-data-root ./datasets/structured_vtoolr1_compare \
  --subset-id vtoolr1_tablevqa_api_same_tools_v1 \
  --evolve-split train \
  --held-out-split val \
  --train-subset-size 200 \
  --held-out-limit 304 \
  --fixed-tool-names focus_on_columns_with_mask focus_on_rows_with_mask focus_on_columns_with_draw focus_on_rows_with_draw \
  --disable-generated-tools \
  --settings direct_vlm toolpool_prompt_baseline skill_only_train_adaptive skill_only_frozen_inference
```

The key row for the main table is `skill_only_frozen_inference`.

## 3A. Local Qwen2.5-VL-32B sanity check on Refocus_Chart

We also ran a larger local backbone through a remote `vLLM` endpoint for a quick same-benchmark check:

- model: `Qwen2.5-VL-32B-Instruct`
- split: full `test` (`826`)
- `direct_vlm`: `67.43%` (`557 / 826`)
- handwritten `skill + bbox tools`: `49.64%` (`410 / 826`)

Result note:

- the handwritten `skill + tool` stack underperformed the direct model
- this suggests the current handwritten SOP/tool orchestration is weaker than the base model on this benchmark
- the result should be treated as a manual baseline, not as a competitive row against `VTool-R1`
- a later per-case probe showed the dominant handwritten failure modes were `empty_answer` and `tool_guided_wrong_answer`, while `direct_vlm` was hurt more by long or truncated responses than by pure visual failure

See:

- [docs/REFOCUS_CHART_QWEN32B_RESULTS.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_QWEN32B_RESULTS.md)
- [docs/reports/refocus_chart_qwen32b_results.json](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/reports/refocus_chart_qwen32b_results.json)
- [docs/REFOCUS_CHART_PROBE.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_PROBE.md)

The handwritten `Refocus_Chart` capability inventory itself is documented in:

- `Manual Capability Inventory` section inside [docs/REFOCUS_CHART_QWEN32B_RESULTS.md](/root/vision_agent_evolve_rl/vision_agent_evolve/docs/REFOCUS_CHART_QWEN32B_RESULTS.md)

## 4. Store the VTool-R1 reported reference

Create one small JSON file per dataset with the reported metric, for example:

```json
{
  "accuracy": 0.717,
  "source": "VTool-R1 paper / official repo"
}
```

Recommended paths:

- `/root/VTool-R1/results/chartqa_vtool_r1_reported.json`
- `/root/VTool-R1/results/refocus_chart_vtool_r1_reported.json`
- `/root/VTool-R1/results/refocus_tablevqa_vtool_r1_reported.json`

## 5. Merge into one comparison payload

ChartQA:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset chartqa \
  --our-summary artifacts/structured_benchmarks/vtoolr1_chartqa_api_same_tools_v1/summary.json \
  --vtool-result /root/VTool-R1/results/chartqa_vtool_r1_reported.json \
  --our-setting skill_only_frozen_inference \
  --reference-label vtool_r1_reported \
  --output artifacts/vtool_r1_comparison/chartqa_api_compare.json
```

ReFOCUS-Chart:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset refocus_chart \
  --our-summary artifacts/structured_benchmarks/vtoolr1_refocus_chart_api_same_tools_v1/summary.json \
  --vtool-result /root/VTool-R1/results/refocus_chart_vtool_r1_reported.json \
  --our-setting skill_only_frozen_inference \
  --reference-label vtool_r1_reported \
  --output artifacts/vtool_r1_comparison/refocus_chart_api_compare.json
```

ReFOCUS-TableVQA:

```bash
python scripts/compare_vtool_r1_results.py \
  --dataset refocus_tablevqa \
  --our-summary artifacts/structured_benchmarks/vtoolr1_tablevqa_api_same_tools_v1/summary.json \
  --vtool-result /root/VTool-R1/results/refocus_tablevqa_vtool_r1_reported.json \
  --our-setting skill_only_frozen_inference \
  --reference-label vtool_r1_reported \
  --output artifacts/vtool_r1_comparison/refocus_tablevqa_api_compare.json
```

The merged payload records:

- direct API baseline
- same-tool prompt baseline
- our same-tool evolve result
- `VTool-R1` reported reference
- non-secret API runtime metadata from our `summary.json`

## 6. VTool code-block protocol check for TableVQA

The VTool-R1 model is trained to emit Python code blocks, not OpenAI native
`tool_calls`. Use this protocol-aligned evaluator for the table comparison:

```bash
python scripts/eval_vtool_protocol.py \
  --data-path /root/VTool-R1/vtool-r1-datasets/table_test.parquet \
  --dataset-type table \
  --output-dir artifacts/vtool_protocol_eval/table_rl_7b_full \
  --base-url http://33.3.175.26:8234/v1 \
  --model VTool-Qwen2.5-7B \
  --num-workers 8
```

Base Qwen under the same VTool prompt/executor:

```bash
python scripts/eval_vtool_protocol.py \
  --data-path /root/VTool-R1/vtool-r1-datasets/table_test.parquet \
  --dataset-type table \
  --output-dir artifacts/vtool_protocol_eval/table_base_7b_full \
  --base-url http://33.3.175.26:8000/v1 \
  --model Qwen2.5-VL-7B-Instruct \
  --num-workers 8
```

Current full-run results on the 304-row table split:

- `VTool-Qwen2.5-7B`: exact `176/304 = 57.89%`, `avg_score = 0.7019`, `tool_usage_rate = 100%`, `tool_exec_success_rate = 75.0%`
- `Qwen2.5-VL-7B-Instruct` with the same VTool prompt/executor: exact `76/304 = 25.0%`, `avg_score = 0.3073`, `tool_usage_rate = 93.75%`, `tool_exec_success_rate = 65.61%`
- Existing base direct structured baseline: exact `173/304 = 56.91%`
- Existing deterministic bbox-prefocus engineering baseline: exact `181/304 = 59.54%`

Interpretation:

- The base model does attempt tool use under the VTool prompt, but its generated code and final-answer format are unstable.
- The failure is not primarily "no tool call"; it is incorrect labels/variables, failed execution, empty answers, and verbose malformed final answers.
- Native OpenAI `tool_calls` should not be used as the main VTool-R1 comparison protocol.

## Code-format vs generic coding probe

To test whether the RL model mainly learned the VTool code protocol rather than broad Python ability, use:

```bash
python scripts/probe_vtool_code_format.py \
  --data-path /root/VTool-R1/vtool-r1-datasets/table_test.parquet \
  --dataset-type table \
  --benchmark-limit 50 \
  --output artifacts/vtool_protocol_eval/table_code_probe_50.json \
  --ignore-proxy-env
```

Default behavior:

- benchmark-side variants:
  - `base_zero`
  - `base_fewshot_2`
  - `base_fewshot_4`
  - `rl_zero`
- generic Python variants:
  - `base_generic`
  - `rl_generic`

The script reuses `eval_vtool_protocol.py` helpers, so the benchmark probe shares:

- the same rendered VTool prompt
- the same python-block parser
- the same tool runtime and bbox aliases
- the same second-rollout logic for successful tool execution

Important note:

- use `--ignore-proxy-env` when your shell still has `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` set, otherwise local `8000` / `8234` calls may silently route through the proxy and fail

## 7. Manual Table Skill Attempt on `8000`

This section records the later attempt to improve TableVQA on the base model
`Qwen2.5-VL-7B-Instruct` at `http://33.3.175.26:8000/v1` using a handwritten
table skill and a small fixed teacher bank.

Important clarification:

- `baseline` in the probe commands below means the base-model variant
  `base_baseline_retrieval_2` on port `8000`
- it does **not** mean the RL model on port `8234`
- the RL reference remains the protocol-aligned full-table run:
  - exact `194/304 = 63.82%`
  - `avg_score = 0.7354`
  - `tool_exec_success_rate = 77.56%`

### Files added for this attempt

- Handwritten teacher bank:
  [manual_vtool_table_teacher_bank.json](/root/vision_agent_evolve_rl/vision_agent_evolve/config/manual_vtool_table_teacher_bank.json)
- Probe/eval harness with manual skill mode:
  [probe_vtool_code_format.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/probe_vtool_code_format.py)

The relevant strategy name in the probe harness is:

- `manual_skill_plus_teacher_examples`

### Manual skill design

The handwritten table skill encoded these policies:

- prefer one-column or one-row focus over longer chains
- inspect whether `columns_bbox` or `rows_bbox` is actually populated before choosing a tool
- for `count_or_total`, focus the value-bearing column first and enumerate qualifying visible entries
- for `comparison`, focus the exact compared rows/items and compute only from the focused values
- require bare `FINAL ANSWER`
- use fixed, hand-cleaned examples instead of dynamic retrieval from RL traces

The fixed teacher bank intentionally covered a few high-frequency table patterns:

- single-column counting
- single-row lookup
- year-row lookup
- row-based binary verification
- simple difference/comparison
- simple extrema lookup

### What was fixed in the implementation

During this attempt, several issues in the probe harness itself were found and fixed:

- `manual_skill_only` / `manual_skill_plus_teacher_examples` now actually use the custom system prompt on the first rollout instead of silently falling back to the plain first rollout path
- fixed teacher examples can now be supplied directly from the JSON file instead of copying noisy RL artifact responses
- the fixed teacher selector now excludes the current target example so smoke runs are not inflated by accidentally few-shotting the same case
- the second-rollout prompt for manual skill variants now explicitly treats the first-pass answer as a candidate to verify rather than something to overwrite casually
- fixed-teacher selection was narrowed so it does not mix too many unrelated families/patterns

### Commands used

Small development probe:

```bash
python scripts/probe_vtool_code_format.py \
  --data-path /root/VTool-R1/vtool-r1-datasets/table_test.parquet \
  --dataset-type table \
  --benchmark-limit 20 \
  --fewshot-counts 2 \
  --prompt-strategies baseline_retrieval manual_skill_plus_teacher_examples \
  --benchmark-variants base_baseline_retrieval_2 base_manual_skill_plus_teacher_examples_2 \
  --skip-generic-code \
  --output /tmp/table_manual_skill_dev20_v5.json \
  --ignore-proxy-env
```

Larger development probe:

```bash
python scripts/probe_vtool_code_format.py \
  --data-path /root/VTool-R1/vtool-r1-datasets/table_test.parquet \
  --dataset-type table \
  --benchmark-limit 50 \
  --fewshot-counts 2 \
  --prompt-strategies baseline_retrieval manual_skill_plus_teacher_examples \
  --benchmark-variants base_baseline_retrieval_2 base_manual_skill_plus_teacher_examples_2 \
  --skip-generic-code \
  --output /tmp/table_manual_skill_dev50_v1.json \
  --ignore-proxy-env
```

### Results

`20`-example development probe after the implementation fixes:

- `base_baseline_retrieval_2`: exact `0.70`, `avg_score = 0.7557`, `tool_exec_success_rate = 0.85`
- `base_manual_skill_plus_teacher_examples_2`: exact `0.70`, `avg_score = 0.7875`, `tool_exec_success_rate = 0.95`

This looked promising, but it did not hold on the larger probe.

`50`-example development probe:

- `base_baseline_retrieval_2`: exact `0.60`, `avg_score = 0.6960`, `tool_exec_success_rate = 0.82`
- `base_manual_skill_plus_teacher_examples_2`: exact `0.52`, `avg_score = 0.6294`, `tool_exec_success_rate = 0.86`

So the handwritten table skill:

- did not beat the existing base-model baseline on the larger development slice
- did not approach the RL reference level
- was not stable enough to justify a full 304-row run in this state

### Main failure pattern observed

The manual-skill variant often succeeded at generating/executing a tool call but
still read the focused image incorrectly in the second rollout. The dominant
error bucket remained:

- `exec_success_but_wrong_answer`

Representative failure modes that remained even after the implementation fixes:

- the model focused the right region but returned a descriptive cell value instead of the requested entity name
- the model recomputed a difference incorrectly after a visually plausible focus
- the model changed an initially reasonable first-pass answer during the second rollout
- the model sometimes overfit to the teaching pattern and forced an unsuitable row/column reasoning program onto a different question

### Current status

This manual table skill attempt is intentionally documented here so another
person can continue from the current state instead of redoing the same work.

The key files to inspect next are:

- [probe_vtool_code_format.py](/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/probe_vtool_code_format.py)
- [manual_vtool_table_teacher_bank.json](/root/vision_agent_evolve_rl/vision_agent_evolve/config/manual_vtool_table_teacher_bank.json)

Recommended next step for whoever takes over:

- split table prompting into at least two tracks instead of one shared handwritten skill:
  - `generic/binary lookup`
  - `count/comparison`
