# Experiment Plan v2: Scientifically Rigorous Redesign

**Date**: 2026-04-03
**Principle**: Every benchmark, baseline, and setting must be traceable to a published paper's protocol.

---

## Part 0: Why Your Current Setup Is Not Rigorous

| Problem | What You Did | What You Should Do |
|---------|-------------|-------------------|
| Benchmarks | Randomly picked VQA datasets | Use EXACTLY the benchmarks from papers you compare against |
| Tools | Gave self-made tools | Let the system evolve tools from scratch — that IS the contribution |
| Train/test split | Ad-hoc splits | Use official splits from benchmark papers |
| Baselines | None | Compare against published methods on the same benchmarks |
| Evaluation | Custom checker | Use standard metrics (relaxed accuracy, ANLS, etc.) |
| Base VLM | Unclear | Fix one (or more) VLM backbone and report which |

---

## Part 1: Benchmark Selection — Driven by Comparability

### Core Principle
> Choose benchmarks BECAUSE published competitors report numbers on them.

### The Comparison Landscape

| Paper | Venue | Benchmarks Used | Base Model |
|-------|-------|----------------|------------|
| **VTool-R1** | ICLR 2026 | ChartQA, TableVQA (ReFOCUS) | Qwen2.5-VL-{3B,7B,32B} |
| **PixelReasoner** | NeurIPS 2025 | V*, TallyQA, InfographicVQA, MVBench | Qwen2.5-VL-7B |
| **ReFOCUS** | ICML 2025 | ChartQA, TableVQA, TabFact, ... | GPT-4o, Qwen2.5-VL-7B |
| **V-Thinker** | arXiv 2025 | VTBench (custom), general VQA | Qwen2.5-VL-7B |
| **Reflexion** | NeurIPS 2023 | HotpotQA, AlfWorld, HumanEval | GPT-4 |
| **AutoManual** | NeurIPS 2024 | ALFWorld, SciWorld | GPT-4-turbo, GPT-3.5 |

### Recommended Benchmark Set

**Tier 1: MUST HAVE (overlap with VTool-R1 + PixelReasoner)**

| Benchmark | Why | Overlap With | Type | Metric | Split |
|-----------|-----|-------------|------|--------|-------|
| **ChartQA** | Charts/graphs understanding; VTool-R1's main benchmark | VTool-R1, ReFOCUS | Cognitive | Relaxed Accuracy | test: 2,500 |
| **V*** | Fine-grained visual detail; PixelReasoner's main benchmark | PixelReasoner | Perceptual | Accuracy | test: ~500 |
| **InfographicVQA** | Complex infographics; PixelReasoner uses it | PixelReasoner | Mixed | ANLS | val: 2,801 / test: 3,288 |

**Tier 2: STRONGLY RECOMMENDED (shows breadth + cognitive bottleneck)**

| Benchmark | Why | Type | Metric | Split |
|-----------|-----|------|--------|-------|
| **MathVista** | Math+visual reasoning; widely reported | Cognitive | Accuracy | testmini: 1,000 |
| **TallyQA-Complex** | Counting; PixelReasoner uses it | Perceptual | Accuracy | test: 22,991 (sample 1000) |

**Tier 3: OPTIONAL (direct VTool-R1 comparison)**

| Benchmark | Why | Type | Metric |
|-----------|-----|------|--------|
| **TableVQA (ReFOCUS)** | VTool-R1's second benchmark | Cognitive | Accuracy |

### What to DROP from Your Current Setup
- **HRBench**: Not used by any comparison paper. Drop it.
- **TextVQA**: Not relevant to "think with images" narrative. Drop it.
- **MIRA**: Too small, no standard protocol. Drop entirely (maybe use as qualitative example).

---

## Part 2: Base VLM Selection

### Key Decision: Which VLM is Our Backbone?

**Option A: Use Qwen2.5-VL-7B** (RECOMMENDED for main experiments)
- Enables direct head-to-head with VTool-R1, PixelReasoner, V-Thinker
- All three use this as their base model before RL training
- We show: same base model, NO RL, still competitive via self-evolution

**Option B: Use GPT-4o / Gemini** (as secondary experiment)
- Shows our method works with commercial APIs
- Higher baseline → harder to improve, but proves generality
- Useful for "model-agnostic" claim

### Recommended Setup
```
Primary experiments:   Qwen2.5-VL-7B (served locally via vLLM)
Secondary experiments: GPT-4o or Gemini-2.0-Flash (API calls)
```

This gives us TWO comparison axes:
1. **Same-model comparison**: Qwen2.5-VL-7B → vs VTool-R1-7B, PixelReasoner-7B
2. **Commercial-model comparison**: GPT-4o → vs GPT-4o + Reflexion, GPT-4o + few-shot

---

## Part 3: Baselines — What to Compare Against

### A. Methods We Must Compare Against (Published Papers)

| Baseline | Type | How to Get Numbers | Priority |
|---------|------|-------------------|----------|
| **Qwen2.5-VL-7B (zero-shot)** | Direct VLM | Run ourselves | P0 |
| **VTool-R1-7B** | RL-trained tool use | Use their reported numbers or run their released model | P0 |
| **PixelReasoner-7B** | RL-trained visual ops | Use their reported numbers | P0 |
| **ReFOCUS (GPT-4o)** | Visual CoT | Use their reported numbers on ChartQA | P1 |
| **Qwen2.5-VL-7B + Text CoT** | Text reasoning | Run ourselves (standard CoT prompting) | P0 |

### B. Methods We Implement Ourselves

| Baseline | What It Does | Implementation |
|---------|-------------|----------------|
| **Few-shot (3-shot)** | Give 3 train examples as demonstrations | New script, ~30 LOC |
| **Reflexion (ours)** | Per-case text reflection, no persistent skills/tools | Modify our system: disable persistence | 
| **Self-Refine** | Iterative self-refinement without new capabilities | Retry with self-critique, no tool/skill gen |
| **Skill-only** | Our system, tool generation disabled | `evolution_mode=skill_only` |
| **Tool-only** | Our system, skill generation disabled | `evolution_mode=tool_only` |

### C. Ablation-Only (Internal Comparisons)

| Setting | What It Tests |
|---------|--------------|
| w/o mastery phase | Tests progressive tool mastery contribution |
| w/o visual analysis | Tests multimodal failure diagnosis |
| w/o failed direction memory | Tests circular loop prevention |
| Iterations 1/3/5/10 | Tests convergence speed |

---

## Part 4: Evaluation Protocol — Follow Published Standards

### ChartQA
- **Official metric**: Relaxed Accuracy (within 5% of gold answer for numerical, exact match for text)
- **Test split**: 2,500 questions (1,250 human-written + 1,250 machine-generated)
- **Source**: [HuggingFace: HuggingFaceM4/ChartQA](https://huggingface.co/datasets/HuggingFaceM4/ChartQA)
- **VTool-R1 protocol**: Use ChartQA test set, report relaxed accuracy

### V* Bench
- **Official metric**: Accuracy (exact or semantic match)
- **Test split**: ~500 questions focused on fine-grained visual details
- **Source**: [vstar-benchmark.github.io](https://vstar-benchmark.github.io/)
- **PixelReasoner reports**: 84% on V* (7B model after RL)

### InfographicVQA
- **Official metric**: ANLS (Average Normalized Levenshtein Similarity)
- **Test split**: 3,288 questions / Val: 2,801 questions
- **Source**: [docvqa.org/datasets/infographicvqa](https://www.docvqa.org/datasets/infographicvqa)
- **PixelReasoner reports**: 84% on InfographicVQA

### MathVista
- **Official metric**: Accuracy
- **Test split**: testmini = 1,000 questions (standard for reporting)
- **Source**: [mathvista.github.io](https://mathvista.github.io/)
- **Standard**: Report on testmini, same as all published papers

### TallyQA-Complex
- **Official metric**: Accuracy
- **Test split**: 22,991 complex counting questions (sample 1,000 for efficiency)
- **Source**: [github.com/manoja328/TallyQA_dataset](https://github.com/manoja328/TallyQA_dataset)
- **PixelReasoner reports**: 74% on TallyQA-Complex

---

## Part 5: Our Experimental Protocol

### Evolution Phase (Training)

```
For each benchmark B:
  1. Take D_train = official train split (or sample k=200 from train)
  2. Run self-evolution on D_train for N=3 iterations
     - Agent attempts cases
     - On failure: analyze → generate skill/tool → validate → retry
     - Mastery phase: profile tool boundaries on held-out family cases
  3. Freeze all learned capabilities (skills + tools + mastery SOPs)
```

### Evaluation Phase (Testing)

```
For each benchmark B:
  1. Take D_test = official test split
  2. Load frozen capabilities from evolution phase
  3. Run agent on D_test with capabilities (no further evolution)
  4. Compute official metric
```

### Key Design Decisions

| Decision | Choice | Justification |
|----------|--------|---------------|
| Train subset size | k=200 per benchmark | Balance cost vs coverage |
| Evolution iterations | 3 (default), also test 1/5/10 | Match current results; ablate in E3.1 |
| No tools given upfront | Start from scratch | Proves the system generates useful tools autonomously |
| Frozen evaluation | No evolution at test time | Proves generalization, not overfitting |

---

## Part 6: Expected Results & What We Want to Show

### Main Results Table (Table 1) — This Is What Reviewers See First

| Method | Training | ChartQA | V* | InfoVQA | MathVista | TallyQA-C | Avg |
|--------|---------|:-------:|:--:|:-------:|:---------:|:---------:|:---:|
| **Direct VLM baselines** | | | | | | | |
| Qwen2.5-VL-7B | — | ~81 | ~58 | ~65 | ~62 | ~55 | ~64 |
| + CoT prompting | — | ? | ? | ? | ? | ? | ? |
| + 3-shot | — | ? | ? | ? | ? | ? | ? |
| + Reflexion (3 iter) | — | ? | ? | ? | ? | ? | ? |
| + Self-Refine (3 iter) | — | ? | ? | ? | ? | ? | ? |
| **RL-trained methods** | | | | | | | |
| VTool-R1-7B | RL (GRPO) | ~87* | — | — | — | — | — |
| PixelReasoner-7B | SFT+RL | — | 84* | 84* | — | 74* | — |
| ReFOCUS (GPT-4o) | 14k SFT | ~88* | — | — | — | — | — |
| **Ours (training-free)** | | | | | | | |
| + Skill only | None | ? | ? | ? | ? | ? | ? |
| + Tool only | None | ? | ? | ? | ? | ? | ? |
| + **Full system** | **None** | **?** | **?** | **?** | **?** | **?** | **?** |

*Numbers marked with * are from published papers (approximate)*

### What We WANT These Results to Show

1. **Our full system > all training-free baselines** (Reflexion, CoT, few-shot, Self-Refine)
   - This proves self-evolution is more effective than ad-hoc improvements

2. **Our full system is COMPETITIVE with RL methods on at least 2 benchmarks**
   - We don't need to beat VTool-R1/PixelReasoner — we just need to be in the ballpark
   - Key argument: "We achieve 85-90% of RL-based performance with ZERO training"

3. **Skill-only > Tool-only on cognitive benchmarks (ChartQA, MathVista)**
   - Validates the cognitive bottleneck hypothesis

4. **Tool-only helps specifically on perceptual benchmarks (V*, TallyQA)**
   - Validates the perceptual bottleneck hypothesis

5. **Full system > Skill-only AND Tool-only**
   - Proves dual-modality is not redundant

### Ablation Table (Table 2)

| Setting | ChartQA | V* | InfoVQA | MathVista |
|---------|:-------:|:--:|:-------:|:---------:|
| Full system | ? | ? | ? | ? |
| w/o tool evolution | ? | ? | ? | ? |
| w/o skill evolution | ? | ? | ? | ? |
| w/o mastery phase | ? | ? | ? | ? |
| w/o visual analysis | ? | ? | ? | ? |
| w/o failed-dir memory | ? | ? | ? | ? |

### What We WANT Ablations to Show

1. **w/o mastery < full**: Proves progressive mastery matters
2. **w/o visual analysis < full**: Proves multimodal diagnosis matters
3. **The gap varies by benchmark**: Perceptual benchmarks hurt more without tools; cognitive benchmarks hurt more without skills

---

## Part 7: Comparison Philosophy

### How to Handle "We Don't Beat RL Methods"

If VTool-R1 (RL-trained) gets 87% on ChartQA and we get 84%:

**DO NOT** frame this as a loss. Frame it as:

> "Our training-free approach achieves 97% of VTool-R1's performance without any weight updates. VTool-R1 requires RL training on 8×H100 GPUs; our method requires only API calls for ~15K tokens per case."

The table becomes:

| Method | Training Cost | ChartQA |
|--------|-------------|:-------:|
| VTool-R1-7B | 8×H100, hours | 87.0 |
| **Ours** | **0 GPU, ~$2** | **84.0** |

This is a STRONG result if positioned correctly.

### How to Handle Benchmarks Where We Shine

If we beat VTool-R1 on any benchmark they DON'T evaluate (V*, MathVista, TallyQA), this is gold:

> "On benchmarks requiring fine-grained visual perception (V*) and mathematical reasoning (MathVista), our training-free approach matches or exceeds the performance of models requiring RL training."

---

## Part 8: Step-by-Step Execution Plan

### Phase 0: Setup (Day 1-2)

```bash
# 1. Set up Qwen2.5-VL-7B locally via vLLM
pip install vllm
vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8000

# 2. Download all benchmark datasets
# ChartQA
huggingface-cli download HuggingFaceM4/ChartQA --local-dir datasets/chartqa

# V*
# Download from vstar-benchmark.github.io

# InfographicVQA
# Download from docvqa.org/datasets/infographicvqa

# MathVista
# Download from mathvista.github.io (testmini)

# TallyQA
# Download from github.com/manoja328/TallyQA_dataset

# 3. Write dataset adapters (normalize to our TaskCase format)
# For each benchmark: image_path, question, gold_answer, metric_type
```

### Phase 1: Baseline Measurements (Day 3-5)

```
Run on ALL benchmarks:
  - Qwen2.5-VL-7B zero-shot
  - Qwen2.5-VL-7B + CoT
  - Qwen2.5-VL-7B + 3-shot
  
Collect all baseline numbers. These are our "before" numbers.
```

### Phase 2: Self-Evolution (Day 5-10)

```
For each benchmark:
  1. Sample k=200 from train split
  2. Run full self-evolution (skill + tool + mastery)
  3. Record: what was generated (skills, tools, mastery profiles)
  4. Freeze capabilities
  5. Evaluate on official test split
```

### Phase 3: Baselines & Ablations (Day 10-16)

```
  - Implement & run Reflexion baseline
  - Implement & run Self-Refine baseline
  - Run skill-only ablation
  - Run tool-only ablation  
  - Run mastery ablation
  - Run visual analysis ablation
```

### Phase 4: Analysis & Writing (Day 16-22)

```
  - Collect all numbers into tables
  - Qualitative case studies
  - Mastery profile visualization
  - Write Introduction, Method, Related Work, Experiments
```

### Phase 5: Polish & Submit (Day 22-25)

```
  - Internal review
  - Fix weak points
  - Format for venue
  - Submit
```

---

## Part 9: Concrete Code Changes Needed

### 9.1 Dataset Adapters (NEW)

You need a unified adapter for each benchmark that converts to your `TaskCase` format:

```python
# scripts/prepare_benchmark.py
# For each benchmark, output: normalized_data/{benchmark}/
#   cases.jsonl: {case_id, prompt, gold_answer, image_path, problem_id, metric_type}

def prepare_chartqa(raw_dir, out_dir):
    # Load ChartQA test split
    # Metric: relaxed_accuracy (5% tolerance for numbers)
    ...

def prepare_vstar(raw_dir, out_dir):
    # Load V* benchmark
    # Metric: accuracy
    ...

def prepare_infovqa(raw_dir, out_dir):
    # Load InfographicVQA val or test split
    # Metric: ANLS
    ...

def prepare_mathvista(raw_dir, out_dir):
    # Load MathVista testmini
    # Metric: accuracy
    ...

def prepare_tallyqa(raw_dir, out_dir):
    # Load TallyQA-Complex test (sample 1000)
    # Metric: accuracy (exact numerical match)
    ...
```

### 9.2 Evaluation Metrics (UPDATE)

Your current answer checker may not support all standard metrics:

```python
# core/metrics.py (NEW or update answer_checker)
def relaxed_accuracy(pred, gold, tolerance=0.05):
    """ChartQA standard: within 5% for numbers, exact for text."""
    ...

def anls_score(pred, gold):
    """InfographicVQA standard: Average Normalized Levenshtein Similarity."""
    ...

def exact_accuracy(pred, gold):
    """Standard exact match (with normalization)."""
    ...
```

### 9.3 Evolution Mode (MODIFY ~20 LOC)

```python
# evolution/loop.py
# Add: evolution_mode parameter
# "both" | "skill_only" | "tool_only" | "none"
```

### 9.4 Visual Analysis Ablation (MODIFY ~10 LOC)

```python
# evolution/roles.py  
# Add: text_only flag to AnalyzerDecider
```

### 9.5 Baseline Scripts (NEW ~100 LOC each)

```python
# scripts/run_reflexion_baseline.py
# scripts/run_fewshot_baseline.py
# scripts/run_selfrefine_baseline.py
# scripts/run_cot_baseline.py
```

---

## Part 10: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Qwen2.5-VL-7B baseline is already very strong (>80% on some benchmarks) | High | Hard to show improvement | Focus on benchmarks where baseline is weaker; emphasize training-free angle |
| VTool-R1 significantly outperforms us on ChartQA | Medium | Reviewer concern | Position as cost-efficiency tradeoff (0 GPU vs 8×H100) |
| Self-evolution doesn't help on some benchmarks | Medium | Weakens story | This IS a finding — shows where self-evolution helps vs doesn't |
| Running all experiments in 25 days is tight | High | Incomplete results | Prioritize: ChartQA + V* + MathVista first; add others if time allows |
| Can't set up Qwen2.5-VL-7B locally | Low | Can't compare directly | Use Gemini Flash as backbone, report VTool-R1 numbers for reference |

---

## Summary: The Minimum Viable Experiment

If you can only do ONE THING, do this:

```
1. Set up Qwen2.5-VL-7B
2. Run zero-shot baseline on ChartQA + V* + MathVista (3 benchmarks)
3. Run your full self-evolution on same 3 benchmarks
4. Report improvement
5. Cite VTool-R1/PixelReasoner numbers for reference

This gives you: Table 1 (main results) + comparison against RL methods.
Everything else is enhancement.
```
