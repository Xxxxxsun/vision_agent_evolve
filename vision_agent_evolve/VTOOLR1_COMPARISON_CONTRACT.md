# VTool-R1 Comparison Contract

**Date**: 2026-04-05  
**Purpose**: Define a fair, decision-complete head-to-head comparison between our training-free evolution framework and `VTool-R1`.

---

## 1. Comparison Question

This experiment answers one narrow question:

> On the same base VLM and the same benchmarks used by `VTool-R1`, can training-free failure-driven evolution reach performance that is competitive with RL-based multimodal tool learning?

This is a **dedicated comparison study**, not the entire paper's experimental scope.

---

## 2. Fairness Rules

### Fixed Comparison Axis

- **Base model**: `Qwen2.5-VL-7B`
- **Benchmarks**: `ChartQA` and `ReFOCUS-TableVQA`
- **Metrics**: the same official metrics used in the compared work
- **Evaluation mode**: frozen test-time inference after evolution

### What Is Held Constant

- Backbone family and size
- Benchmark dataset and split
- Metric definition
- Reported result granularity: benchmark-level final scores

### What Is Allowed to Differ

- `VTool-R1`: RL-trained tool-use policy with a provided tool set
- `Ours`: training-free failure-driven evolution with self-generated skills/tools plus mastery

This difference is the point of the comparison and must be stated explicitly in the paper.

---

## 3. Required Result Rows

The comparison table must include these rows:

| Row | Description | Source |
|-----|-------------|--------|
| `Qwen2.5-VL-7B direct` | Vanilla model, no evolution | Run ourselves |
| `Qwen2.5-VL-7B + strong prompting` | Best non-RL prompt-only baseline we can fairly implement | Run ourselves |
| `VTool-R1-7B` | RL-trained visual tool-use method | Use reported or released-model result |
| `Ours (full evolve)` | Skill + tool + mastery, no weight updates | Run ourselves |

Optional rows if budget allows:

- `Ours (skill only)`
- `Ours (tool only)`
- `Ours (w/o mastery)`

These are useful for analysis but are not required for the core head-to-head claim.

---

## 4. Target Claims

This experiment is allowed to support only these claims:

1. Our training-free method is competitive with an RL-based multimodal tool-use method under a same-base comparison.
2. Our method does not require weight updates, RL infrastructure, or retraining.
3. If performance is slightly lower, the result is still positive if the cost and implementation burden are much lower.

This experiment is **not** allowed to support:

- "Our method is best across all modern VLMs"
- "Qwen2.5-VL-7B is our only or main backbone everywhere"
- "Our method beats every RL-based approach universally"

---

## 5. Execution Order

### Step 1: Lock protocol

- Confirm exact `ChartQA` and `ReFOCUS-TableVQA` dataset variants and splits
- Confirm official metric implementation for each
- Confirm what `VTool-R1` reports for `7B`

### Step 2: Establish our non-RL floor

- Run `Qwen2.5-VL-7B direct`
- Run one strong prompt-only baseline on the same setup

### Step 3: Run our method on the same setup

- Evolve on train split or approved train subset
- Freeze learned capabilities
- Evaluate once on the official evaluation split

### Step 4: Build comparison table

- Report absolute score
- Report delta over vanilla `Qwen2.5-VL-7B`
- Report distance to `VTool-R1`
- Report compute/training-cost note alongside the table

---

## 6. Output Format

The main comparison table should follow this structure:

| Method | Training | ChartQA | ReFOCUS-TableVQA | Notes |
|--------|----------|:-------:|:----------------:|-------|
| Qwen2.5-VL-7B direct | None | ? | ? | vanilla |
| Qwen2.5-VL-7B + strong prompting | None | ? | ? | prompt-only baseline |
| VTool-R1-7B | RL | reported | reported | same backbone |
| Ours (full evolve) | None | ? | ? | skill + tool + mastery |

The prose under the table must explain:

- same-base fairness
- RL vs training-free mechanism difference
- whether our gain over vanilla closes a meaningful fraction of the RL gap

---

## 7. Acceptance Criteria

This comparison study is ready only if all of the following are true:

- The benchmark protocol matches the compared paper
- The base model is exactly `Qwen2.5-VL-7B`
- We have at least one strong non-RL baseline besides vanilla
- Our method is evaluated with frozen capabilities
- The final writeup avoids over-claiming beyond this comparison axis
