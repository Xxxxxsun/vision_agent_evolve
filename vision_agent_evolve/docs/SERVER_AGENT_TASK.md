# Server Agent Task: Fix Table VQA Crop Tool Usage

## Background

We are trying to make Qwen2.5-VL-7B-Instruct use `crop_to_columns` / `crop_to_rows` tools
when answering table VQA questions, instead of the older `focus_on_columns_with_draw` tools.

Current results (v3, 20 cases):
- `base_zero`: 12/20 = **60.0%** (no examples, baseline)
- `base_manual_skill_plus_teacher_examples_4`: 10/20 = **50.0%** ← WORSE than baseline
- `rl_zero`: 16/20 = 80.0%

**Root problem**: The model never uses `crop_to_columns` (verified: `crop_in_code=0` for all variants).
Despite the jinja examples being updated to use crop tools, the model still uses `focus_on_*` tools.

---

## Step 1: Verify server has latest jinja

```bash
grep -c "crop_to_columns" /root/VTool-R1-fork/examples/format_prompt/chartQA.jinja
```

Expected output: `4` (four crop_to_columns calls in examples).

If output is `0` or less than 4:
```bash
cd /root/VTool-R1-fork && git pull origin main
```

---

## Step 2: Diagnose — see what the model actually generates

Add `--verbose` flag and save one raw response. Alternatively, add temporary debug logging
to the probe script to print `generated_code` per case:

In `/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/probe_vtool_code_format.py`,
find where `second_rollout_used` is set in the per-case result dict, and add:
```python
"generated_code": first_response_text,  # or whatever variable holds the raw model output
```
This lets us verify what tool the model actually calls.

Alternatively, run a one-shot debug:
```bash
python3 -c "
import sys
sys.path.insert(0, '/root/vision_agent_evolve_rl/vision_agent_evolve')
# quick single inference to check what tool model uses
from openai import OpenAI
client = OpenAI(base_url='http://33.3.175.26:8000/v1', api_key='EMPTY')
jinja = open('/root/VTool-R1-fork/examples/format_prompt/chartQA.jinja').read()
# strip the jinja template marker and use as system prompt
prompt = jinja.split('\"\"\"', 1)[-1].split('\"\"\"')[0]
resp = client.chat.completions.create(
    model='Qwen2.5-VL-7B-Instruct',
    messages=[{'role':'user','content': prompt + '\n# USER REQUEST #: How many rows have value X?\n# RESULT #:'}],
    max_tokens=200
)
print(resp.choices[0].message.content)
"
```

---

## Step 3: The real fix — remove focus_on_* tools from jinja docs

**Hypothesis**: Even though all 4 examples now use `crop_to_columns`, the jinja still documents
6 `focus_on_*` functions (lines 12-136 of chartQA.jinja). The model sees those docs and
defaults to the familiar `focus_on_*` tools. 

**Fix**: In `/root/VTool-R1-fork/examples/format_prompt/chartQA.jinja`, delete the docstrings
for all `focus_on_*` functions and keep ONLY `crop_to_columns` and `crop_to_rows`.

The block to DELETE is everything from:
```
def focus_on_columns_with_highlight(image, ...
```
through:
```
    \"\"\"
```
of `focus_on_rows_with_draw` — i.e., lines 12–136 in the current file.

Keep only:
```python
def crop_to_columns(image, columns_to_show, all_columns_bounding_boxes):
    """
    Crop the image to ONLY the specified columns ...
    """

def crop_to_rows(image, rows_to_show, all_rows_bounding_boxes):
    """
    Crop the image to the header row plus ONLY the specified data rows ...
    """
```

After this edit, commit and push from the LOCAL machine (MacBook), then on the server:
```bash
cd /root/VTool-R1-fork && git pull origin main
```

---

## Step 4: Re-run probe after fix

```bash
cd /root/vision_agent_evolve_rl/vision_agent_evolve
python scripts/probe_vtool_code_format.py \
  --data-path /root/vqa_datasets/datasets/refocus_hf/table_test.parquet \
  --dataset-type table \
  --benchmark-limit 20 \
  --output /tmp/table_crop_v4_dev20.json \
  --prompt-strategies manual_skill_plus_teacher_examples
```

Expected: `crop_to_columns` appears in generated code, accuracy > 60%.

---

## Step 5: Also fix — add `generated_code` to per-case output

So we can debug future runs. In `probe_vtool_code_format.py`, find the per-case result dict
(search for `"failure_bucket"`) and add the raw model output text for the first rollout.

---

## Summary of files to modify

| File | Location | Change |
|---|---|---|
| `chartQA.jinja` | `/root/VTool-R1-fork/examples/format_prompt/chartQA.jinja` | Delete all `focus_on_*` function docstrings (lines 12–136), keep only `crop_to_columns` and `crop_to_rows` |
| `probe_vtool_code_format.py` | `/root/vision_agent_evolve_rl/vision_agent_evolve/scripts/probe_vtool_code_format.py` | Add `"generated_code"` field to per-case result dict |
