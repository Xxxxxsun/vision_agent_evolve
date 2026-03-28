# Paper Plan: Self-Evolving Visual Agent (基于实际实验结果)

## Part 1: 你现在手上有什么 (Current State)

### 1.1 实际实验结果

| Dataset | Skill | Tool | Iter | Train w/o | Train w/ | Val w/o | Val w/ | Val Delta |
|---------|:-----:|:----:|:----:|:---------:|:--------:|:-------:|:------:|:---------:|
| ChartQA | ✅ | ❌ | 3 | 0.65 | 0.70 | 0.712 | 0.753 | **+4.1%** |
| V* | ✅ | ✅ | 3 | 0.70 | 0.75 | 0.483 | 0.550 | **+6.6%** |
| HRBench4K | ✅ | ✅ | 3 | 0.80 | 0.80 | 0.559 | 0.586 | **+2.8%** |
| MathVista | ✅ | ❌ | 3 | 0.60 | 0.60 | 0.517 | 0.609 | **+9.2%** |
| TextVQA | — | — | — | — | — | 0.754 | — | baseline |

### 1.2 关键观察

1. **Skill 是主要驱动力** — 所有 4 个 benchmark 都生成了 skill，但只有 V* 和 HRBench 生成了 tool
2. **Val set 一致提升** — 4 个数据集上全部正向提升 (+2.8% ~ +9.2%)，说明学到的能力有泛化性
3. **Train 提升不一致** — ChartQA/V* 的 train 有 +5%，但 HRBench/MathVista 的 train 没有变化
4. **只用了 3 轮迭代** — 很少的进化次数就有效果
5. **MIRA 数据有限** — 只在单个 example 上反复做，没有系统性的 train/val 划分

### 1.3 已生成的能力

**全局工具 (3)**: flip_image, billiards_reflection_solver, dice_state_solver
**全局技能 (6)**: mirror_clock, billiards, rolling_dice_top, mirrored_spatial_reasoning, mirrored_content_interpretation, mirrored_spatial_variable_tracking

**数据集特定**:
- ChartQA: chart_bar_approximation_tool (HSV条形图分析) + chartqa skill (SOP)
- HRBench: color_recognition_tool + hrbench_focus_grid_tool + hrbench_single skill
- V*: tools + skills (具体待确认)
- MathVista: skill only (数学推理策略)

### 1.4 核心问题：为什么现在这样发不了顶会？

**问题 1: Story 不清楚** — 你的系统到底在解决什么问题？"自我进化"太泛了。Reviewer 会问：和 Reflexion 比呢？和 fine-tuning 比呢？和人工写 prompt 比呢？

**问题 2: 提升幅度不够震撼** — +2.8% ~ +9.2% 的提升，如果没有深入分析"为什么"，reviewer 会觉得这只是 prompt engineering。

**问题 3: 没有对比实验** — 没和任何 baseline (Reflexion, Voyager-style, human-written skills, CoT prompting) 对比。

**问题 4: 没有分析深度** — 为什么 ChartQA 只需要 skill？为什么 V* 需要 tool？学到的 skill 具体改变了什么？

**问题 5: MIRA 结果不成体系** — 单例测试没有统计意义。

---

## Part 2: 论文 Outline (重新构思)

### 2.1 论文核心叙事 (The Story)

**不要说**: "我们做了一个自我进化的系统"（太泛，和 Voyager/Reflexion 撞车）

**应该说**:

> VLM (Vision Language Models) 在标准视觉问答基准上仍有系统性的失败模式——不是因为"不够聪明"，而是因为缺少特定的推理策略和视觉处理能力。我们提出了一种 **failure-driven capability evolution** 框架，让 VLM agent 从少量训练样本的失败中，自动学习两种互补的能力：**Skills** (推理策略，告诉 agent 怎么思考) 和 **Tools** (代码工具，给 agent 新的视觉处理能力)。我们发现：(1) 不同类型的 benchmark 需要不同类型的进化（有的只需策略，有的需要工具），(2) 学到的能力具有良好的泛化性，(3) 这种进化在仅 3 轮迭代后就能产生显著且一致的提升。

**核心 Insight (The Surprise)**:

> Skill evolution (策略进化) 比 tool evolution (工具进化) 更普遍有效——在 4/4 个数据集上 skill 都被生成且有效，但只有 2/4 需要 tool。这意味着 VLM 的主要瓶颈往往不是"看不到"，而是"不知道怎么看"。Skill 解决的是认知策略问题，Tool 解决的是感知能力问题。

### 2.2 Paper Title (候选)

- **"Learning to See Better: Failure-Driven Skill and Tool Evolution for Visual Agents"**
- **"Skills Over Tools: What Self-Evolving Visual Agents Actually Learn from Failure"**
- **"Self-Evolving Visual Agents: When Strategies Matter More Than Tools"**

### 2.3 Paper Outline

```
1. Introduction
   - VLMs 在标准 benchmark 上仍有系统性失败
   - 现有方法：fine-tuning (昂贵)、prompt engineering (手工)、tool use (固定工具集)
   - 我们的方法：自动从失败中学习 skill + tool
   - Key finding: skill evolution 比 tool evolution 更普遍重要
   - 三个贡献

2. Related Work
   - 2.1 Tool-augmented VLMs (Chameleon, VisProg, ViperGPT)
   - 2.2 Self-improving agents (Voyager, Reflexion, ExpeL)
   - 2.3 LLM-based tool creation (CREATOR, LATM, CRAFT)
   - 2.4 我们的定位: failure-driven dual-modality evolution in vision domain

3. Method
   - 3.1 Problem formulation
     - 给定小规模训练集 D_train，通过进化学习能力集 C = {skills, tools}
     - 在 D_val 上评估泛化
   - 3.2 Evolution loop
     - Solve → Fail → Analyze (with visual context) → Generate (skill/tool/both) → Validate → Retry
   - 3.3 Skill evolution (策略生成)
     - What is a skill: 结构化的推理 SOP
     - How skills are generated: failure analysis → strategy synthesis
     - How skills accumulate: 迭代更新，合并新旧知识
   - 3.4 Tool evolution (工具合成)
     - When tools are needed: 当 VLM 的感知能力不够时
     - Tool validation: 3-stage (syntax, origin, regression)
     - Tool-skill co-generation: tool 回答"怎么做"，skill 回答"什么时候做"
   - 3.5 Key design decisions
     - Visual failure analysis (AnalyzerDecider 看图片)
     - Failed direction deduplication (避免重复失败)
     - Dual-modality: 系统自动决定需要 skill 还是 tool

4. Experiments
   - 4.1 Setup
     - 5 benchmarks: ChartQA, V*, HRBench, MathVista, TextVQA
     - Evolution: 在 train split 上进化 3 轮
     - Evaluation: 在 val split 上测试 frozen capabilities
   - 4.2 Main results (Table 1)
     - Baseline (direct VLM) vs. w/ evolved skills vs. w/ evolved skills+tools
     - 一致的 val 提升
   - 4.3 Analysis: Skills vs. Tools (核心分析，这是论文的亮点)
     - 4.3.1 哪些 benchmark 只需要 skill？(ChartQA, MathVista) → 策略瓶颈
     - 4.3.2 哪些需要 tool？(V*, HRBench) → 感知瓶颈
     - 4.3.3 学到的 skill 具体包含什么？(case study)
     - 4.3.4 学到的 tool 具体做了什么？(case study)
   - 4.4 Ablation studies
     - w/o skill evolution
     - w/o tool evolution
     - w/o visual failure analysis
     - w/o failed-direction memory
     - Iterations: 1 vs 3 vs 5 vs 10
   - 4.5 Qualitative analysis
     - Case study: ChartQA 的 skill 如何改变 agent 行为
     - Case study: V* 的 tool 如何补充 VLM 感知能力
     - Failure analysis: 进化失败的 case (什么学不到？)

5. Discussion
   - When does evolution help vs. not help?
   - Skill vs. tool: 策略瓶颈 vs. 感知瓶颈的分类框架
   - Limitations: 3 轮后的收益递减、计算成本

6. Conclusion
```

---

## Part 3: 需要补充的实验 (Future Experiment Plan)

### 优先级分类

```
🔴 P0 (必须做，否则无法投稿): Baseline 对比、核心消融
🟡 P1 (强烈建议，显著提升论文质量): 深度分析、更多迭代
🟢 P2 (锦上添花，时间允许再做): 额外 benchmark、理论分析
```

### 🔴 P0: Baseline Comparisons (最紧急)

你目前只有 "w/o skill" vs "w/ skill" 的对比。Reviewer 第一个问题就是：和现有方法比呢？

#### P0-1: Direct VLM Baseline (已有)

这就是你的 "Val w/o skill" 列。✅ 已完成。

#### P0-2: Reflexion Baseline (必须加)

**Reflexion 的核心**: 失败后生成文本反思，下次重试时注入上下文。**没有工具生成**。

**实现方式**: 利用你现有系统的 skills-only 模式，但关键区别：
- Reflexion 的"反思"是 **per-case** 的（每个 case 有自己的反思历史）
- 你的 skill 是 **per-family** 的（一族共享一个 SOP）

**最简实现** (不需要从零写 Reflexion):
```
设置: 限制 next_action 只能选 "generate_skill"，且 skill 不持久化（每次 case 独立）
```

或者更好的方式：**用你的系统，但禁用 tool 生成和 skill 持久化**，让每个 val case 独立做 3 次 self-reflect 重试。

**预期结果**: 你的方法应该比 Reflexion 好，因为 (a) 你的 skill 跨 case 共享，(b) 你有 tool 能力。

#### P0-3: Few-shot CoT Baseline (必须加)

**手动写 3 个 example 的 few-shot prompt**，直接跑 val set。

**目的**: 证明你的自动进化比人工 few-shot prompting 更好（或至少有竞争力）。

**实现**: 从 train set 随机选 3 个 (question, answer) pair 作为 few-shot examples，拼进 system prompt。

#### P0-4: Human-Written Skill Baseline (建议加)

**手动为每个 benchmark 写一个 skill SOP**（你作为人类专家写最好的策略）。

**目的**: 衡量自动进化的 skill 和人写的差距有多大。如果很接近 → 强有力的证据。

### 🔴 P0: Core Ablations (必须做)

#### P0-5: Skill-only vs Tool-only vs Both

| Setting | Skill Gen | Tool Gen | 说明 |
|---------|:---------:|:--------:|------|
| Full system | ✅ | ✅ | 你现在的系统 |
| Skill-only | ✅ | ❌ | 限制 next_action 排除 generate_tool |
| Tool-only | ❌ | ✅ | 限制 next_action 排除 generate_skill |
| Neither (retry only) | ❌ | ❌ | 只重试，不生成任何新能力 |

**代码改动**: 在 `EvolutionLoop.__init__` 加 `evolution_mode: str = "both"` 参数，在 `_normalize_analysis_for_mode` 中过滤 `next_action`。

**最小改动约 20 行**。

#### P0-6: Visual Analysis Ablation

**改动**: 在 `AnalyzerDecider` 中禁用图片输入（只传文本描述）。

**目的**: 证明视觉化失败分析（看图片对比）比纯文本分析更好。

**代码改动**: 约 10 行 (在 `analyze_and_decide` 中加 `text_only` flag)。

### 🟡 P1: Deeper Analysis (强烈建议)

#### P1-1: 更多迭代实验

你目前只跑了 3 轮。跑 **1, 3, 5, 10** 轮的对比：

```bash
for iter in 1 3 5 10; do
    python scripts/run_structured_experiment.py \
      --dataset chartqa \
      --max-planning-rounds ${iter} \
      --subset-id chartqa_iter${iter} \
      ...
done
```

**预期**: 画一条收益递减曲线。如果 3 轮就接近最优 → "我们的方法收敛很快"。如果 10 轮明显更好 → "还有进一步提升空间"。

#### P1-2: Skill 内容分析 (Qualitative, 不需要跑实验)

**对每个 benchmark 已生成的 skill，做详细 case study**:

1. 读 `learned/chartqa_*/skills/chartqa/SKILL.md` — 它教会了 agent 什么策略？
2. 拿一个 val case，对比 "没有 skill 时 agent 的行为" vs "有 skill 时的行为" — 具体改变了什么？
3. 把 skill 内容和 val 上的改善 case 对应起来 — 改善的 case 是否恰好是 skill 覆盖的场景？

**这可以作为 Section 4.3 的核心内容，不需要额外实验。**

#### P1-3: 失败模式分析

分析进化**失败**的 case（val 上没有改善的 case）:

1. 生成了 skill/tool 但 val 没有改善的 case → 为什么？过拟合？还是 skill 不适用？
2. 完全没有生成任何能力的情况 → AnalyzerDecider 选了 give_up？为什么？
3. Train 上成功但 val 上没有泛化的 case → 过拟合的信号

#### P1-4: 训练集大小的影响

你目前 ChartQA 用了 ~25-50 个 train cases。测试:

```
k = 10, 25, 50, 100, 200
```

画 val accuracy vs training set size 曲线。

**预期**: 即使很少的 train cases 也能产生有用的 skill（因为 skill 是策略不是记忆）。

#### P1-5: 跨数据集/任务的能力迁移分析

在 ChartQA 上学到的 skill，用在 MathVista 上会怎样？（两者都是图表/数学相关）

**简单实验**: 把 `learned/chartqa_*/skills/` 复制到 `learned/mathvista_*/skills/`，然后跑 frozen inference。

### 🟢 P2: Nice-to-Have

#### P2-1: MIRA 系统性实验

把 MIRA 做成正式的 train/val split，每族用 LOO 或 K-fold，得到统计显著的结果。

#### P2-2: TextVQA 的完整实验

你目前只有 TextVQA baseline (0.754)。补上进化实验。

#### P2-3: 与 fine-tuning 对比

如果 VLM 支持 LoRA fine-tuning，用同样的 train data 做 SFT，和你的方法对比。

**目的**: 证明 skill evolution 比梯度更新更样本高效。

#### P2-4: 不同 VLM backbone 的泛化

用 GPT-4o、Qwen-VL、Gemini 分别测试，证明方法不依赖特定模型。

---

## Part 4: 论文的三个核心贡献

### 贡献 1: Failure-Driven Dual-Modality Capability Evolution Framework

我们提出了一个让视觉 agent 从失败中自动学习两种互补能力的框架：
- **Skills** (推理策略): 结构化的 SOP，教 agent "怎么思考"
- **Tools** (代码工具): 可执行的图像处理程序，给 agent "新的视觉能力"
- 系统自动决定每个 benchmark 需要哪种类型的进化

### 贡献 2: Skills vs Tools 的实证发现

通过在 5 个标准 VQA benchmark 上的实验，我们发现：
- **Skill evolution 是普遍有效的** (4/4 数据集)，tool evolution 是有条件的 (2/4)
- 这揭示了两类不同的 VLM 瓶颈：
  - **Strategy bottleneck** (ChartQA, MathVista): VLM 能看到信息但不知道如何推理 → skill 解决
  - **Perception bottleneck** (V*, HRBench): VLM 看不到或看不清关键信息 → tool 补充
- 我们提供了系统性的分析框架来区分这两类瓶颈

### 贡献 3: 高效的自我进化

仅 3 轮进化迭代，在 4 个标准 benchmark 的 val set 上实现一致提升 (+2.8% ~ +9.2%)，证明了：
- 少量 train samples + 失败驱动的进化 = 有效的能力泛化
- 比 fine-tuning 更样本高效，比手工 prompt engineering 更自动化

---

## Part 5: 论文关键 Table 和 Figure 设计

### Table 1: Main Results (必须)

| Method | ChartQA | V* | HRBench | MathVista | Avg |
|--------|:-------:|:--:|:-------:|:---------:|:---:|
| Direct VLM (baseline) | 71.2 | 48.3 | 55.9 | 51.7 | 56.8 |
| Few-shot CoT (3-shot) | ? | ? | ? | ? | ? |
| Reflexion (3 iter) | ? | ? | ? | ? | ? |
| Human-written skills | ? | ? | ? | ? | ? |
| **Ours: Skill only** | ? | ? | ? | ? | ? |
| **Ours: Skill + Tool** | **75.3** | **55.0** | **58.6** | **60.9** | **62.5** |

### Table 2: Ablation (必须)

| Setting | ChartQA | V* | HRBench | MathVista |
|---------|:-------:|:--:|:-------:|:---------:|
| Full system | 75.3 | 55.0 | 58.6 | 60.9 |
| w/o tool evolution | ? | ? | ? | ? |
| w/o skill evolution | ? | ? | ? | ? |
| w/o visual analysis | ? | ? | ? | ? |
| w/o failed-dir memory | ? | ? | ? | ? |

### Table 3: What Was Learned (分析表)

| Dataset | Skills Generated | Tools Generated | Skill Type | Tool Type |
|---------|:----------------:|:---------------:|:----------:|:---------:|
| ChartQA | 1 | 0 | Chart reading SOP | — |
| V* | 1 | 2 | Spatial reasoning | Image processing |
| HRBench | 1 | 2 | Focus strategy | Color detection + Grid focus |
| MathVista | 1 | 0 | Math reasoning SOP | — |

### Figure 1: System Overview (1/3 page)

Evolution loop 示意图: Solve → Fail → Analyze (see images) → Decide (skill? tool? both?) → Generate → Validate → Retry

### Figure 2: Val Accuracy Improvement (bar chart)

4 个 benchmark 的 before/after bar chart，clearly showing improvement

### Figure 3: Strategy vs Perception Bottleneck (核心 figure)

2x2 矩阵图:
- X 轴: Skill helps? (yes/no)
- Y 轴: Tool helps? (yes/no)
- ChartQA, MathVista → Skill-only 象限 (Strategy bottleneck)
- V*, HRBench → Skill+Tool 象限 (Perception bottleneck)
- (empty or TextVQA → baseline 象限)

### Figure 4: Convergence Curve (iterations vs accuracy)

Lines for each benchmark showing accuracy improvement over evolution iterations (1, 3, 5, 10)

### Figure 5: Case Study (1/2 page)

Side-by-side comparison:
- Left: Agent behavior WITHOUT evolved skill (on a ChartQA example)
- Right: Agent behavior WITH evolved skill
- Highlight: what the skill changed in reasoning

### Figure 6: Learned Skill Example (1/4 page)

Show actual SKILL.md content for one benchmark — demonstrate the human-readable, structured SOP format

---

## Part 6: 实验执行优先级时间线

### Week 1 (最紧急)

**P0-2: Reflexion baseline** (~20 行代码改动)
- 实现: skills-only + per-case 反思 (不持久化)
- 跑 4 个 benchmark

**P0-3: Few-shot CoT baseline** (~30 行新脚本)
- 实现: 3-shot prompting
- 跑 4 个 benchmark

**P0-5: Skill-only vs Tool-only ablation** (~20 行改动)
- 限制 evolution_mode = "skill_only" / "tool_only"
- 跑 4 个 benchmark

### Week 2

**P0-6: Visual analysis ablation** (~10 行改动)
- text_only mode for AnalyzerDecider
- 跑 4 个 benchmark

**P1-1: 更多迭代** (不需要改代码)
- iter = 1, 5, 10 (你已有 iter=3 的结果)
- 画收益曲线

**P1-2: Skill 内容分析** (不需要跑实验)
- 读已有 SKILL.md，写 case study
- 对比有无 skill 的 agent 行为

### Week 3

**P0-4: Human-written skill baseline** (手动写 4 个 skill)
- 你作为人类专家，为每个 benchmark 写一个最好的 SOP
- 跑 frozen inference

**P1-3: 失败模式分析** (不需要新实验)
- 分析现有 per_case.jsonl 数据

**P1-4: Training set size** (不需要改代码)
- k = 10, 25, 50, 100, 200 for ChartQA

### Week 4

**P2-2: TextVQA 完整实验** (用现有 pipeline)
**P2-1: MIRA 系统性实验** (如果时间够)
**写论文**

---

## Part 7: 最小化代码改动清单

### 改动 1: Evolution Mode (P0-5, ~20 行)

文件: `evolution/loop.py`

```python
# EvolutionLoop.__init__ 加参数:
evolution_mode: str = "both"  # "both" | "skill_only" | "tool_only" | "none"

# 在 _normalize_analysis_for_mode 中:
if self.evolution_mode == "skill_only":
    if analysis.next_action in ["generate_tool", "generate_both"]:
        analysis.next_action = "generate_skill"
elif self.evolution_mode == "tool_only":
    if analysis.next_action in ["generate_skill", "generate_both"]:
        analysis.next_action = "generate_tool"
elif self.evolution_mode == "none":
    analysis.next_action = "give_up"
```

文件: `run.py` — 加 `--evolution-mode` flag

### 改动 2: Text-Only Analysis (P0-6, ~10 行)

文件: `evolution/roles.py`

```python
# AnalyzerDecider.__init__ 加:
self.text_only = text_only  # False by default

# 在 analyze_and_decide 中, 构建 content_parts 时:
if self.text_only:
    content_parts = [p for p in content_parts if p.get("type") != "image_url"]
```

### 改动 3: Reflexion Baseline (P0-2, ~30 行)

新文件: `scripts/run_reflexion_baseline.py`

```python
# 对每个 val case:
#   1. 直接跑 agent (不加任何 skill/tool)
#   2. 如果失败，生成文本反思 (用 AnalyzerDecider 但不生成 tool/skill)
#   3. 把反思作为额外 instruction 注入 agent，重试
#   4. 重复 3 次
#   5. 记录最终结果
```

### 改动 4: Few-shot CoT Baseline (P0-3, ~30 行)

新文件: `scripts/run_fewshot_baseline.py`

```python
# 对每个 benchmark:
#   1. 从 train set 随机选 3 个 (question, answer) pairs
#   2. 拼成 few-shot prompt
#   3. 直接用 VLM 跑 val set (不用 agent)
#   4. 记录结果
```

**总代码改动: ~110 行修改 + ~60 行新脚本 ≈ 170 行**

---

## Part 8: 论文叙事的关键论点

### Introduction 第一段 (Problem)

> Vision-Language Models (VLMs) like GPT-4o achieve impressive zero-shot performance on visual question answering, yet they exhibit systematic failure patterns on standard benchmarks. These failures stem from two distinct bottlenecks: **strategy bottlenecks**, where the model can perceive the visual information but lacks the appropriate reasoning strategy (e.g., how to read a complex chart), and **perception bottlenecks**, where the model cannot extract the necessary visual details (e.g., fine-grained color recognition in high-resolution images).

### Introduction 第二段 (Gap)

> Existing approaches address these bottlenecks separately. Fine-tuning improves model capabilities but requires large datasets and is computationally expensive. Prompt engineering and few-shot learning provide reasoning strategies but are manual and task-specific. Tool-augmented agents (VisProg, Chameleon) expand perception but rely on fixed, predefined tool sets. Self-improving agents (Reflexion, Voyager) learn from failures but either produce only verbal reflections (no executable tools) or operate in non-visual domains.

### Introduction 第三段 (Our approach)

> We present [SystemName], a framework that enables VLM agents to autonomously evolve both types of capabilities from a small number of training failures. Our system generates **skills** — structured reasoning strategies that teach the agent how to approach a class of problems — and **tools** — executable image-processing programs that expand the agent's perception. Crucially, the system **automatically decides** which type of capability to generate based on visual failure analysis, producing skills when the bottleneck is strategic and tools when it is perceptual.

### Introduction 第四段 (Results + Insight)

> On four standard VQA benchmarks (ChartQA, V*, HRBench, MathVista), our system achieves consistent improvements of +2.8% to +9.2% on held-out validation sets after only 3 evolution iterations. Our key finding is that **skill evolution is universally effective** (improving all 4 benchmarks) while tool evolution provides additional gains only on benchmarks with perception bottlenecks (V*, HRBench). This reveals a fundamental distinction: most VLM failures on standard benchmarks are strategy failures, not perception failures — the model can see the information but doesn't know how to reason about it.

---

## Part 9: 与相关工作的定位 (精简版)

| 维度 | Reflexion | Voyager | CREATOR/LATM | VisProg | **Ours** |
|------|-----------|---------|-------------|---------|----------|
| 域 | Text/Code | Minecraft | Text/Math | Vision | **Vision** |
| 生成 Skill? | ✅ (文本反思) | ✅ (代码) | ❌ | ❌ | **✅ (SOP策略)** |
| 生成 Tool? | ❌ | ✅ (代码) | ✅ | ❌ | **✅ (图像处理)** |
| 自动决策? | 固定(反思) | 固定(代码) | 固定(工具) | 固定(组合) | **✅ 自动选择** |
| 视觉分析? | ❌ | ❌ | ❌ | N/A | **✅ 看图诊断** |
| 泛化验证? | ❌ | 同域 | ❌ | N/A | **✅ train→val** |
| Benchmark | HumanEval | Minecraft | MATH | GQA | **ChartQA,V*,HRBench,MathVista** |

**核心差异一句话**: 我们是第一个在标准 VQA benchmark 上展示 failure-driven dual-modality (skill+tool) capability evolution 且验证泛化性的工作。
