# Run Commands — Manual Skill & Tool Variants

## 模型切换

```bash
# GPT-4o
export VLM_MODEL="gpt-4o"

# GPT-5.4（阿里内部）
export VLM_API_STYLE="alibaba_chat"
export VLM_BASE_URL="https://llm-chat-api.alibaba-inc.com/v1/api/chat"
export VLM_MODEL="gpt-5.4-0305-global"
export VLM_USER_ID="506759"
export VLM_ACCESS_KEY="9101ac974ab20f60f668dcf099bc6a10"
export VLM_QUOTA_ID="dd95187c-29dd-464d-9b96-8f62e6ab8eb5"
export VLM_APP="model_train_vlm"
```

---

## 变体说明

| 变体 | Skill | Tool | 命令关键参数 |
|------|-------|------|-------------|
| Baseline | 无 | 无 | `--settings reasoned_vlm` |
| Skill + Tool | 详细 skill | 有 | `--settings function_calling_vqa` |
| Skills-only | 详细 skill | 无 | `--capability-root ./skills_no_tools --settings function_calling_vqa --disable-fc-tools` |
| Tools + minimal skill | 极简 skill | 有 | `--capability-root ./skills_minimal --settings function_calling_vqa` |

---

## ChartQA

```bash
# 1. Baseline
python scripts/run_structured_experiment.py \
  --dataset chartqa --raw-data-root "/root/vqa_datasets/datasets/chartqa_hf" \
  --normalized-data-root ./datasets/structured_chartqa \
  --subset-id chartqa_baseline_gpt4o_v1 \
  --evolve-split val --train-subset-size 1920 --settings reasoned_vlm

# 2. Skill + Tool
python scripts/run_structured_experiment.py \
  --dataset chartqa --raw-data-root "/root/vqa_datasets/datasets/chartqa_hf" \
  --normalized-data-root ./datasets/structured_chartqa \
  --subset-id chartqa_skill_tool_gpt4o_v1 \
  --evolve-split val --train-subset-size 1920 --settings function_calling_vqa

# 3. Skills-only（无工具，详细 skill）
python scripts/run_structured_experiment.py \
  --dataset chartqa --raw-data-root "/root/vqa_datasets/datasets/chartqa_hf" \
  --normalized-data-root ./datasets/structured_chartqa \
  --subset-id chartqa_skills_only_gpt4o_v1 \
  --capability-root ./skills_no_tools \
  --evolve-split val --train-subset-size 1920 \
  --settings function_calling_vqa --disable-fc-tools

# 4. Tools + minimal skill
python scripts/run_structured_experiment.py \
  --dataset chartqa --raw-data-root "/root/vqa_datasets/datasets/chartqa_hf" \
  --normalized-data-root ./datasets/structured_chartqa \
  --subset-id chartqa_tools_minimal_gpt4o_v1 \
  --capability-root ./skills_minimal \
  --evolve-split val --train-subset-size 1920 --settings function_calling_vqa
```

---

## HRBench

```bash
# 1. Baseline
python scripts/run_structured_experiment.py \
  --dataset hrbench --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_baseline_gpt4o_v1 \
  --evolve-split val --train-subset-size 700 --settings reasoned_vlm

# 2. Skill + Tool
python scripts/run_structured_experiment.py \
  --dataset hrbench --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_skill_tool_gpt4o_v1 \
  --evolve-split val --train-subset-size 700 --settings function_calling_vqa

# 3. Skills-only（无工具，详细 skill）
python scripts/run_structured_experiment.py \
  --dataset hrbench --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_skills_only_gpt4o_v1 \
  --capability-root ./skills_no_tools \
  --evolve-split val --train-subset-size 700 \
  --settings function_calling_vqa --disable-fc-tools

# 4. Tools + minimal skill
python scripts/run_structured_experiment.py \
  --dataset hrbench --raw-data-root /root/vqa_datasets/datasets/hr_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id hrbench_tools_minimal_gpt4o_v1 \
  --capability-root ./skills_minimal \
  --evolve-split val --train-subset-size 700 --settings function_calling_vqa
```

---

## MathVista

```bash
# 1. Baseline
python scripts/run_structured_experiment.py \
  --dataset mathvista --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_baseline_gpt4o_v1 \
  --evolve-split val --train-subset-size 900 --settings reasoned_vlm

# 2. Skill + Tool
python scripts/run_structured_experiment.py \
  --dataset mathvista --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_skill_tool_gpt4o_v1 \
  --evolve-split val --train-subset-size 900 --settings function_calling_vqa

# 3. Skills-only（无工具，详细 skill）
python scripts/run_structured_experiment.py \
  --dataset mathvista --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_skills_only_gpt4o_v1 \
  --capability-root ./skills_no_tools \
  --evolve-split val --train-subset-size 900 \
  --settings function_calling_vqa --disable-fc-tools

# 4. Tools + minimal skill
python scripts/run_structured_experiment.py \
  --dataset mathvista --raw-data-root /root/vqa_datasets/datasets/mathvista \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id mathvista_tools_minimal_gpt4o_v1 \
  --capability-root ./skills_minimal \
  --evolve-split val --train-subset-size 900 --settings function_calling_vqa
```

---

## VStar

```bash
# 1. Baseline
python scripts/run_structured_experiment.py \
  --dataset vstar --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_baseline_gpt4o_v1 \
  --evolve-split val --train-subset-size 151 --settings reasoned_vlm

# 2. Skill + Tool
python scripts/run_structured_experiment.py \
  --dataset vstar --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_skill_tool_gpt4o_v1 \
  --evolve-split val --train-subset-size 151 --settings function_calling_vqa

# 3. Skills-only（无工具，详细 skill）
python scripts/run_structured_experiment.py \
  --dataset vstar --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_skills_only_gpt4o_v1 \
  --capability-root ./skills_no_tools \
  --evolve-split val --train-subset-size 151 \
  --settings function_calling_vqa --disable-fc-tools

# 4. Tools + minimal skill
python scripts/run_structured_experiment.py \
  --dataset vstar --raw-data-root /root/vqa_datasets/datasets/vstar_bench \
  --normalized-data-root ./datasets/structured_multibench \
  --subset-id vstar_tools_minimal_gpt4o_v1 \
  --capability-root ./skills_minimal \
  --evolve-split val --train-subset-size 151 --settings function_calling_vqa
```
