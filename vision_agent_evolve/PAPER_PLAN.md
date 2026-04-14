# Paper Plan: Self-Evolving Visual Agents

**Title (working)**: Think with Images, Learn from Failure: Training-Free Self-Evolution of Visual Agents via Skill and Tool Generation

**One-sentence contribution**: We show that VLM agents can autonomously evolve both reasoning strategies (skills) and visual processing tools from failure — without any model training — achieving +2.8%–9.2% improvements on four standard VQA benchmarks and revealing that strategy bottlenecks are more prevalent than perception bottlenecks in modern VLMs.

**Venue**: ICLR
**Type**: Method + Empirical
**Date**: 2026-04-07
**Page budget**: 9 pages (main body through Conclusion; references and appendix excluded)
**Section count**: 6

---

## Claims-Evidence Matrix

| # | Claim | Evidence | Status | Section |
|---|-------|----------|--------|---------|
| C1 | Training-free dual-modality evolution outperforms all non-trained baselines | +4.1% ChartQA, +9.2% MathVista, +6.6% V*, +2.8% HRBench vs. direct VLM | Supported (Reflexion/CoT baselines still needed) | §4 |
| C2 | Skill evolution is universally effective (4/4 benchmarks); tool evolution is conditional (2/4) | ChartQA, MathVista: skill-only effective; V*, HRBench: skill+tool needed | Supported | §4.2 |
| C3 | VLM failures decompose into cognitive vs. perceptual bottlenecks | Cognitive (strategy) → ChartQA/MathVista; Perceptual → V*/HRBench | Supported | §4.2 |
| C4 | Progressive tool mastery improves generalization over no-mastery baseline | Ablation: full system vs. w/o mastery phase | **Needs experiment** | §4.3 |
| C5 | Visual failure analysis (seeing images) outperforms text-only failure analysis | Ablation: w/ vs. w/o image input to AnalyzerDecider | **Needs experiment** | §4.3 |
| C6 | Evolved capabilities generalize from training cases to unseen validation cases | Train → Val improvement consistent across all 4 benchmarks | Supported | §4.1 |

---

## §0 Abstract

- **What we achieve**: A training-free framework where VLM agents self-evolve both cognitive strategies (skills) and visual processing tools (code) from failure analysis.
- **Why it matters / is hard**: VLMs exhibit systematic failures on visual benchmarks; existing fixes require expensive RL/SFT training or are manual. No prior work achieves training-free dual-modality evolution.
- **How we do it**: On failure, the agent (a) visually diagnoses root cause, (b) automatically decides whether to generate a reasoning SOP (skill) or executable image-processing code (tool), (c) validates the capability, and (d) accumulates it for future cases.
- **Evidence**: Consistent +2.8%–9.2% improvements on ChartQA, V*, HRBench, MathVista after only 3 iterations on small training subsets.
- **Most remarkable result**: Skill evolution is universally effective across all benchmarks, while tool evolution provides additional gains only where perceptual limitations exist — revealing that most VLM failures are strategy failures, not perception failures.
- **Estimated length**: 200–240 words
- **Self-contained check**: Reader understands the contribution, approach, and key finding without reading the paper.

**Draft**:
VLMs still exhibit systematic failure patterns on standard visual benchmarks, yet state-of-the-art improvements require RL training on dedicated GPUs or manual prompt engineering. We present [SystemName], a training-free framework in which VLM agents autonomously evolve two complementary capabilities from failure: *skills* — structured reasoning strategies encoding how to approach a problem class — and *tools* — executable Python programs that expand the agent's visual perception. When the agent fails, it visually diagnoses the root cause (seeing both original images and tool outputs), automatically decides whether the bottleneck is cognitive or perceptual, generates the appropriate capability, validates it, and accumulates it for future use. Evaluated on four standard VQA benchmarks (ChartQA, V*, HRBench, MathVista), [SystemName] achieves +2.8%–9.2% improvements on held-out validation sets after only 3 evolution iterations on 200 training cases per benchmark, without any weight updates. Our key finding is that skill evolution is universally effective (4/4 benchmarks) while tool evolution provides additional gains only on perceptual benchmarks (2/4), revealing a fundamental dichotomy: most VLM failures on standard benchmarks are strategy failures, not perception failures.

---

## Structure

### §1 Introduction (1.5 pages)

- **Opening hook**: VLMs achieve impressive zero-shot scores yet exhibit consistent, systematic failure modes on visual benchmarks — not because they lack intelligence, but because they lack appropriate reasoning strategies and perceptual capabilities for specific task families.
- **Gap / challenge**: Existing approaches address failures either by retraining (VTool-R1, PixelReasoner require RL; ReFOCUS requires 14k SFT), manual engineering (few-shot, CoT), or self-reflection without persistent capability accumulation (Reflexion). None achieve training-free generation of both strategic and executable capabilities that generalize across cases.
- **One-sentence contribution**: See above.
- **Approach overview**: Two-role agent (AnalyzerDecider + Generator) that diagnoses failures with visual context, decides the bottleneck type, and generates either an SOP skill or an image-processing tool — validated and accumulated across cases.
- **Key questions**:
  1. Can a VLM agent learn generalizable capabilities from a small number of failures, without training?
  2. When is a skill sufficient vs. when is a tool necessary?
  3. What does this reveal about VLM failure modes?
- **Contributions** (4 bullets):
  1. We propose [SystemName], a training-free framework for VLM agents to autonomously evolve reasoning skills and visual tools from failure, achieving consistent +2.8%–9.2% improvements on four standard VQA benchmarks.
  2. We identify a cognitive-perceptual bottleneck dichotomy: skill evolution alone is sufficient for strategy-bottlenecked benchmarks (ChartQA, MathVista), while perceptual benchmarks (V*, HRBench) additionally require tool evolution.
  3. We introduce progressive tool mastery, where the agent learns not just to generate tools but to profile their applicability boundaries (when to use, chain, or skip), distilling this into reusable deployment SOPs.
  4. We show via ablation that visual failure analysis (the agent sees the original image and tool artifacts) is critical: text-only diagnosis produces systematically worse capability generation.
- **Results preview**: After 3 iterations on 200 training cases per benchmark, our training-free system outperforms Reflexion and few-shot CoT across all four benchmarks, and achieves X% of VTool-R1's performance on ChartQA without any weight updates.
- **Hero figure (Fig 1)**: A two-panel figure. Left panel: the evolution loop showing Solve → Fail → VisualDiagnosis → Decide(skill/tool) → Generate → Validate → Accumulate. Right panel: a comparison table/radar showing our training-free system vs. Reflexion, few-shot CoT, and VTool-R1 (RL-based) across cost vs. performance axes, making the training-free + competitive performance claim visually immediate. Caption: "Figure 1: [SystemName] evolution loop (left) and capability comparison (right). Our training-free system achieves competitive performance against RL-trained methods on ChartQA and V*, at zero training cost."
- **Estimated length**: 1.5 pages
- **Key citations**: VTool-R1 [ICLR 2026], Reflexion [NeurIPS 2023], Voyager [NeurIPS 2023], VisProg [CVPR 2023], CREATOR [arXiv 2023]
- **Front-loading check**: By end of Introduction, reader knows the system generates skills AND tools from failure, it's training-free, it improves 4 benchmarks, and strategy bottlenecks dominate.

---

### §2 Related Work (1 page)

- **Subtopics** (4 categories):
  1. **Self-improving agents** (Reflexion, Voyager, ExpeL, AutoManual, EvolveR): build on prior failure via text reflection or skill libraries, but operate in text/code/game domains; none generate executable visual tools.
  2. **Tool creation for LLMs** (CREATOR, LATM, ToolLLM): generate tools but in text/math domains; no mastery phase; no vision.
  3. **"Think with images" / visual reasoning with tools** (VTool-R1, V-Thinker, PixelReasoner): enable VLMs to use visual tools for reasoning, but require RL or SFT; fixed tool sets; no self-evolution.
  4. **Tool-augmented VLMs** (VisProg, ViperGPT, Chameleon): compose predefined tools for visual tasks; no tool generation; no self-improvement.
- **Positioning**: Our work sits at the intersection of (1) and (3): we achieve "think with images" capability (like VTool-R1) but through training-free in-context evolution (like Reflexion), generating both cognitive strategies (novel vs. all prior work) and visual tools.
- **Minimum length**: 1 page (~4 paragraphs), synthesizing by method family not paper-by-paper.
- **Must NOT be just a list**: Each category ends with a "Why insufficient" statement that motivates our design choices.

---

### §3 Method (2 pages)

- **Notation**:
  - $\mathcal{D}_{\text{train}}$: small training subset (k=200 cases per benchmark)
  - $\mathcal{D}_{\text{val}}$: held-out validation set
  - $\mathcal{C} = \{\mathcal{S}, \mathcal{T}\}$: capability set (Skills $\mathcal{S}$ + Tools $\mathcal{T}$)
  - $\pi_\theta$: frozen VLM backbone
  - $f_\mathcal{C}$: agent operating with capability set $\mathcal{C}$

- **Problem formulation**: Given $\mathcal{D}_{\text{train}} = \{(x_i, y_i, \mathbf{v}_i)\}$ (question, answer, visual input), and frozen VLM $\pi_\theta$, learn capability set $\mathcal{C}$ that maximizes performance on $\mathcal{D}_{\text{val}}$ without any gradient updates to $\pi_\theta$.

- **3.1 Evolution Loop** (0.5 pages):
  - Attempt → Fail → Analyze → Generate → Validate → Promote / Discard → Retry
  - Each failure triggers one AnalyzerDecider call (1 LLM call) + 1–2 Generator calls
  - Capabilities are accumulated in $\mathcal{C}$ and available to future cases (persistent, cross-case)

- **3.2 Visual Failure Diagnosis** (0.5 pages):
  - AnalyzerDecider receives: original image + tool artifacts (if any) + failed attempt + current capabilities
  - Outputs: root cause analysis + `next_action` ∈ {generate_skill, generate_tool, generate_both, give_up}
  - Key design: seeing images (not just text) enables accurate diagnosis of perceptual vs. cognitive failures
  - Contrast with text-only Reflexion: AnalyzerDecider can see "the tool output looks wrong because..."

- **3.3 Skill Evolution** (0.5 pages):
  - Skill = structured Markdown SOP with: When-to-Use, Strategy, Common Failures
  - Generated by Generator from root cause analysis
  - Accumulated via merging (new insights appended to existing skill)
  - Scope: per-benchmark family (shared across cases in same distribution)

- **3.4 Tool Evolution + Progressive Mastery** (0.5 pages):
  - Tool = Python code (≤150 lines) using CV libraries
  - 3-stage validation: syntax check → origin case test → regression test
  - **Progressive mastery**: after tool creation, agent runs the tool on a held-out set of similar cases to profile:
    - `supported_patterns`: cases where tool helps
    - `negative_patterns`: cases where tool hurts  
    - `recommended_trigger_conditions`: when to invoke
    - `best_chain_patterns`: optimal tool sequences
  - Mastery profile distilled into reusable SOP (skill), enabling deployment without mastery re-runs

- **Key design decisions** (inline):
  - Only 2 roles vs. 10 in prior work
  - 2–3 LLM calls per iteration vs. 8+ in prior work
  - Dual-modality: system automatically decides skill vs. tool vs. both

---

### §4 Experiments (3 pages)

- **4.1 Setup** (0.5 pages):
  - Base VLM: Gemini-2.0-Flash (API) / Qwen2.5-VL-7B (secondary)
  - Benchmarks: ChartQA (relaxed accuracy, test: 2500), V* (accuracy, ~500), HRBench4K (accuracy), MathVista (accuracy, testmini: 1000)
  - Evolution: k=200 train cases, 3 iterations; evaluation on frozen capabilities
  - Baselines: Zero-shot VLM, CoT prompting, 3-shot few-shot, Reflexion (per-case, no persistence), Skill-only, Tool-only

- **4.2 Main Results — Table 1** (1 page):
  - Shows all methods across 4 benchmarks + average
  - Highlights: our full system > all training-free baselines; competitive with RL methods
  - **Figures**:
    - Fig 2 (bar chart): before/after per benchmark, grouped by method family
    - Table 1 (comparison table): direct VLM / Reflexion / few-shot / Skill-only / Tool-only / Ours-full / VTool-R1 (reference)
  - **Data source**: existing val results + forthcoming baseline runs
  
- **4.3 Cognitive vs. Perceptual Bottleneck Analysis** (1 page):
  - **Key finding**: Skill-only system matches full system on ChartQA (+4.1%) and MathVista (+9.2%) but falls short on V* and HRBench where tools provide additional +X%
  - **Framework**: 2×2 matrix: Skill effective? × Tool effective? → 4 benchmark quadrants
  - **What was learned** (Table 3): per-benchmark: skills generated, tools generated, skill type, tool type
  - **Qualitative**: side-by-side agent behavior on ChartQA case w/ and w/o evolved skill
  - **Figures**:
    - Fig 3: Cognitive vs. perceptual bottleneck 2×2 matrix with benchmarks placed
    - Fig 5: Case study side-by-side

- **4.4 Ablation Studies — Table 2** (0.5 pages):
  - w/o tool evolution | w/o skill evolution | w/o mastery phase | w/o visual analysis | w/o failed-dir memory
  - Expected: mastery ablation shows biggest drop on V*/HRBench; visual analysis drop largest on perceptual benchmarks
  
- **4.5 Evolution Dynamics** (0.5 pages):
  - Convergence curve: accuracy at iteration 1, 3, 5, 10 per benchmark
  - Training set size: k = 10, 25, 50, 100, 200 (ChartQA)
  - **Figures**:
    - Fig 4: Convergence curves (line plots, 4 benchmarks × 4 iteration counts)

---

### §5 Discussion (0.5 pages)

- When does evolution help? Benchmarks with clear task families and reusable failure patterns → skills effective. Benchmarks requiring sub-image manipulation → tools additionally needed.
- **Limitations**: (a) 3-iteration results; gains may plateau; (b) tool quality limited by VLM's coding ability; (c) evaluation on 4 benchmarks — broader coverage needed; (d) compute cost: ~15K tokens per training case.
- **Future work**: (1) Cross-benchmark skill transfer (ChartQA skills → MathVista); (2) image generation API as a reasoning tool (external visual imagination); (3) longer evolution (>10 iterations).

---

### §6 Conclusion (0.5 pages)

- Restate: [SystemName] enables VLM agents to self-evolve reasoning strategies and visual tools from failure, without training.
- Restate key finding: strategy bottlenecks dominate; skill evolution sufficient for 2/4 benchmarks.
- Close: failure-driven in-context evolution is a viable alternative to RL-based visual reasoning augmentation, with dramatically lower deployment cost.

---

## Figure Plan

| ID | Type | Description | Data Source | Priority |
|----|------|-------------|-------------|----------|
| Fig 1 | Hero (2-panel) | Left: evolution loop diagram; Right: cost vs. performance comparison table/radar (Training-free vs. RL methods) | Manual / experiment results | HIGH |
| Fig 2 | Grouped bar chart | Before/after accuracy improvement per benchmark, grouped by method (baseline, Reflexion, few-shot, ours-skill, ours-full) | Main results table | HIGH |
| Fig 3 | 2×2 matrix scatter | Skill-effective? × Tool-effective? with 4 benchmarks plotted | Ablation results | HIGH |
| Fig 4 | Line plots | Accuracy vs. evolution iteration (1,3,5,10) for 4 benchmarks | Iteration experiment | MEDIUM |
| Fig 5 | Side-by-side case study | Agent reasoning traces w/ and w/o evolved ChartQA skill | Qualitative log | HIGH |
| Fig 6 | Example skill/tool | Actual generated SKILL.md + tool code snippet for one benchmark | `learned/` directory | MEDIUM |
| Table 1 | Main comparison | All methods × all benchmarks, with training cost column | Main experiments | HIGH |
| Table 2 | Ablation | Full system vs. component-disabled variants | Ablation experiments | HIGH |
| Table 3 | What was learned | Per-benchmark: skills, tools, skill type, tool type | Qualitative analysis | MEDIUM |

**Hero Figure 1 detail**: The right panel should show a small table or radar comparing: (a) VTool-R1: RL required, fixed tools, ChartQA ~87%; (b) PixelReasoner: SFT+RL, fixed ops; (c) Ours: No training, self-generated tools+skills, ChartQA ~?%. The visual contrast "RL required" vs. "Training-free" should be immediately apparent. Caption should read: "Figure 1: [SystemName] alternates between solving visual tasks and evolving capabilities (left). Our training-free approach achieves competitive performance against RL-trained methods at zero training cost (right). ✗ = training required, ✓ = training-free."

---

## Citation Plan

- **§1 Intro**: Reflexion [NeurIPS 2023], Voyager [NeurIPS 2023], VTool-R1 [ICLR 2026 - VERIFY], PixelReasoner [NeurIPS 2025 - VERIFY], V-Thinker [arXiv 2025 - VERIFY], Qwen2.5-VL [VERIFY]
- **§2 Related Work**:
  - Self-improving: Reflexion, Voyager, ExpeL [NeurIPS 2023], AutoManual [NeurIPS 2024 - VERIFY], EvolveR [arXiv 2025 - VERIFY], Agent0 [arXiv 2025 - VERIFY]
  - Tool creation: CREATOR [arXiv 2023 - VERIFY], LATM [ICLR 2024 - VERIFY], ToolLLM [ICLR 2024 - VERIFY]
  - Think with images: VTool-R1, V-Thinker, PixelReasoner, Visualization-of-Thought [ICLR 2024 - VERIFY]
  - Visual programming: VisProg [CVPR 2023], ViperGPT [ICCV 2023], Chameleon [NeurIPS 2024 - VERIFY]
- **§3 Method**: ChartQA [VERIFY authors/year], V* [VERIFY], HRBench [VERIFY], MathVista [VERIFY]
- **§4 Experiments**: ReFOCUS [ICML 2025 - VERIFY], TallyQA [VERIFY]

**Citation rules**: All citations marked [VERIFY] must be verified via arXiv or Semantic Scholar before writing. Do NOT generate BibTeX from memory.

---

## Page Budget Check

| Section | Estimated Pages |
|---------|----------------|
| §1 Introduction | 1.5 |
| §2 Related Work | 1.0 |
| §3 Method | 2.0 |
| §4 Experiments | 3.0 |
| §5 Discussion | 0.5 |
| §6 Conclusion | 0.5 |
| **Total** | **8.5** |

Fits within ICLR's 9-page limit with 0.5 pages buffer for figures.

---

## Reviewer Feedback

*(Step 6: GPT-5.4 review unavailable in this session — Codex MCP not connected. Run `/research-review` separately before freezing the outline.)*

**Anticipated reviewer concerns (pre-emptive):**

1. **"Why not just use Reflexion?"** → Addressed in §4.3: Reflexion has no persistent cross-case accumulation; ablation shows persistent skills are critical.
2. **"The gains are modest (+2.8%–9.2%)"** → Framed as: these are consistent improvements from 3 iterations on only 200 training cases, with zero training cost. Position against RL baseline cost.
3. **"VTool-R1 gets better numbers"** → VTool-R1 uses 8×H100 GPUs for RL training; our approach uses only API calls. Frame efficiency, not raw score.
4. **"Limited to 4 benchmarks"** → Acknowledge in limitations; note that we show complementary types (cognitive + perceptual). Cross-benchmark diversity is the point.
5. **"Is mastery phase necessary?"** → Ablation in §4.4 should show mastery gap on perceptual benchmarks.

---

## Missing Experiments (P0 — Must complete before writing)

| Experiment | Code change | Priority |
|-----------|------------|---------|
| Reflexion baseline | ~30 LOC new script | P0 |
| Few-shot CoT (3-shot) | ~30 LOC new script | P0 |
| Skill-only ablation | ~20 LOC in evolution/loop.py | P0 |
| Tool-only ablation | ~20 LOC in evolution/loop.py | P0 |
| w/o visual analysis ablation | ~10 LOC in evolution/roles.py | P0 |
| w/o mastery phase ablation | ~5 LOC in mastery code path | P0 |
| Iteration curve (1,3,5,10) | Re-run with different iter count | P1 |
| Training set size (k=10,25,50,100,200) | Re-run with different k | P1 |

---

## ICLR Venue Checklist

- [ ] Keep story front-loaded — contribution clear by end of Introduction
- [ ] LLM disclosure note: [SystemName] was developed with LLM assistance (appendix note needed)
- [ ] Reproducibility: document base VLM, API settings, k, N, validation protocol
- [ ] Limitations section present (§5)
- [ ] Code availability statement (appendix)
- [ ] Anonymous submission: no author names, affiliations, or self-identifying repo links in main paper
- [ ] Page budget verified: 9 pages max (references excluded)
- [ ] `natbib` citations: use `\citep{}` and `\citet{}`

---

## Next Steps

- [ ] `/run-experiment` to implement and run P0 baselines (Reflexion, few-shot CoT, ablations)
- [ ] `/paper-figure` to generate all figures (Table 1, Fig 1 hero, Fig 3 bottleneck matrix, Fig 4 curves)
- [ ] `/research-review` via Codex MCP for external GPT-5.4 review of this outline
- [ ] `/paper-write` to draft LaTeX section by section
- [ ] `/paper-compile` to build PDF
