# MathVista Pulled Gate Doubao Results

Run timestamp: `20260504T142458Z_mathvista_pulled_gate`

Code baseline:

- `894b736 Fix MathVista tool gate: default to full tools, remove hardcoded whitelist`

Model endpoint configuration:

- `VLM_API_STYLE=alibaba_chat`
- `VLM_BASE_URL=https://llm-chat-api.alibaba-inc.com/v1/api/chat`
- `VLM_MODEL=doubao-seed-2.0-pro`
- `VLM_APP=llm_application`
- `VLM_QUOTA_ID=79b2a6c6-f7c6-4138-aae0-abaa3b1608e5`

Dataset:

- `mathvista` val split
- 900 cases
- raw data root: `/root/vqa_datasets/datasets/mathvista`
- normalized root: `./datasets/structured_multibench`

## Results

| Variant | Subset ID | Correct / Total | Accuracy | Tool Cases | Runtime Errors |
| --- | --- | ---: | ---: | ---: | ---: |
| `skill_tool` | `mathvista_skilltool_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate` | 792 / 900 | 0.8800 | 619 | 0 |
| `tool_only` | `mathvista_toolonly_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate` | 784 / 900 | 0.8711 | 581 | 0 |

## Tracked Artifacts

Structured benchmark outputs:

- `artifacts/structured_benchmarks/mathvista_skilltool_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate/summary.json`
- `artifacts/structured_benchmarks/mathvista_skilltool_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate/per_case.jsonl`
- `artifacts/structured_benchmarks/mathvista_skilltool_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate/train_subset_manifest.json`
- `artifacts/structured_benchmarks/mathvista_toolonly_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate/summary.json`
- `artifacts/structured_benchmarks/mathvista_toolonly_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate/per_case.jsonl`
- `artifacts/structured_benchmarks/mathvista_toolonly_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate/train_subset_manifest.json`

Rollout logs:

- `artifacts/batch_runs/20260504T142458Z_mathvista_pulled_gate/logs/mathvista_skilltool_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate.log`
- `artifacts/batch_runs/20260504T142458Z_mathvista_pulled_gate/logs/mathvista_toolonly_doubaoseed20pro_pulledgate_val_full_20260504T142458Z_mathvista_pulled_gate.log`

Large per-case `function_calling_vqa/` working directories were intentionally not tracked.
