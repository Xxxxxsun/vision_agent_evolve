# Vision Agent Self-Evolution Project - Analysis & Redesign Plan

**Date**: 2026-03-13
**Analyzer**: Claude Sonnet 4.5
**Status**: Planning Phase

---

## 1. 项目目标 (User's Goal)

### 核心期望
创建一个**自我进化的视觉Agent**系统，能够：

1. **解决视觉Puzzle问题** (如MIRA数据集)
2. **在单个例子上循环迭代**，直到成功
3. **自动生成Tool和Skill**来弥补能力缺口
4. **从失败中学习**，不断改进策略

### 关键要求
- 当一个例子失败时，分析原因
- 从不同方向尝试(生成tool/skill)
- 持续改进，直到打通这个例子
- 学到的能力可复用到其他例子

### 参考项目
- **Glue_SWE** (原有项目) - VLM Agent + 自我进化框架
- **autoresearch** (Andrej Karpathy) - 自我进化思想的参考

---

## 2. 现有项目分析

### 2.1 Glue_SWE 深度分析

#### 项目规模
- 总代码量: ~10,057行
- 核心模块 `glue_swe/`: ~10,000行
- 自我进化 `self_evolve/`: ~2,100行 (21%)
- 工具实现 `tools/`: ~5,200行 (52%)

#### 架构设计

```
Glue_SWE/
├── agent_core/              # 基础模型 (~300行)
│   ├── models.py           # ToolSchema, ToolResult等
│   ├── llm_client.py       # VLMClient
│   └── __init__.py
│
├── glue_swe/               # 核心Agent (~10,000行)
│   ├── agent.py            # SWEAgent - ReAct循环 (216行)
│   ├── llm.py              # OpenAI客户端 (111行)
│   ├── converter.py        # 响应解析 (185行)
│   ├── skills.py           # Skill发现和渲染 (112行)
│   ├── tool_registry.py    # Tool注册和调度 (151行)
│   │
│   ├── self_evolve/        # 自我进化模块 (~2,100行)
│   │   ├── loop.py         # 主循环 (519行) ⚠️
│   │   ├── contracts.py    # 数据契约 (275行)
│   │   ├── store.py        # 能力存储 (395行)
│   │   ├── validation.py   # 验证引擎 (117行)
│   │   ├── runtime.py      # 执行上下文 (234行)
│   │   │
│   │   └── roles/          # 角色系统 (~1,400行) ⚠️
│   │       ├── analyzer.py        # 失败分析 (162行)
│   │       ├── decider.py         # 决策制定 (143行)
│   │       ├── tool_generator.py  # Tool生成 (144行)
│   │       ├── skill_generator.py # Skill生成 (~150行)
│   │       ├── reviewer.py        # 提案审查 (202行)
│   │       ├── solver.py          # 任务求解 (143行)
│   │       ├── judge.py           # 评估判断 (~100行)
│   │       ├── summarizer.py      # 经验总结 (~150行)
│   │       ├── skill_refiner.py   # Skill优化 (123行)
│   │       └── planner.py         # 规划器 (278行, 已过时)
│   │
│   ├── tools/              # 工具实现 (~5,200行)
│   │   ├── defuse_bomb_cv/       # 纯CV (2,185行) ⚠️
│   │   ├── defuse_bomb_hybrid/   # CV+VLM (1,626行) ⚠️
│   │   └── mirror_clock_hybrid/  # 镜像时钟 (808行)
│   │
│   └── skills_swe/         # 预加载技能
│       ├── defuse_a_bomb/SKILL.md
│       └── mirror_clock/SKILL.md
```

#### 核心机制

**1. VLM Agent (SWEAgent)**
- **设计模式**: ReAct (Reasoning + Acting)
- **工具访问**: 仅通过`bash` action
- **循环流程**:
  ```
  For each turn (max 20):
    1. LLM生成响应
    2. 解析Action JSON
    3. 执行bash命令
    4. 返回Observation
    5. 继续对话
  ```
- **多模态**: 支持图像附加到LLM请求
- **输出截断**: 6000字符限制(前3000+后3000)

**2. Skill机制**
- **本质**: YAML Frontmatter + Markdown文档
- **作用**: 注入系统提示，指导Agent行为
- **加载**: 从`skills_swe/`扫描SKILL.md
- **渲染**: 组合成"Preloaded Skills"部分

示例结构:
```markdown
---
name: mirror_clock
description: "Solve mirror_clock tasks through CLI tools only."
---

## Mandatory Rules
- Use command line actions only
- Preferred tool: `mirror_clock_answer_with_restore`

## Standard Command
python -m glue_swe.tool_cli mirror_clock_answer_with_restore \
  --args-json '{"image_path":"...","question":"..."}'
```

**3. Tool机制**
- **本质**: 可执行Python代码
- **调用方式**: 通过CLI (`python -m glue_swe.tool_cli`)
- **返回格式**: JSON (`{status, text, payload, artifacts, error}`)
- **内置工具**:
  - `defuse_bomb_hybrid_solve`
  - `defuse_bomb_solve`
  - `mirror_clock_answer_with_restore`
  - `mirror_clock_restore`

**4. 自我进化循环**

完整流程 (每个失败case):
```
1. Baseline Solve (Solver)
   ↓ 失败
2. Analyze Failure (LLMAnalyzer)
   → FailureAnalysis:
     - root_cause
     - missing_capabilities
     - needed_tool_role
   ↓
3. Decide Next Step (LLMDecider)
   → PlannerDecision:
     - action: noop | skill | tool | tool_and_skill
   ↓
4. Generate Capabilities
   - Tool: LLMToolGenerator → ToolProposal (Python code)
   - Skill: LLMSkillGenerator → SkillProposal (Markdown)
   ↓
5. Review & Repair (LLMProposalReviewer)
   → ProposalReview (修复语法错误)
   ↓
6. Validate (ValidationEngine)
   - syntax_ok (AST parse)
   - load_ok (import test)
   - contract_ok (manifest check)
   - origin_case_ok (解决原case?) ← 关键
   - regression_ok (不破坏已解决case?)
   - skill_ok (文档有效?)
   ↓
7. Promote or Discard
   - 通过 → candidates/ → promoted/
   - 失败 → 记录，继续尝试
   ↓
8. Refine Skill (LLMSkillRefiner)
   - 优化文档表达
   - 合并到canonical_skill.md
   ↓
9. Retry with New Capabilities
```

**角色系统 (10个LLM驱动的角色):**
1. **Analyzer** - 分析失败原因
2. **Decider** - 决策修复策略
3. **ToolGenerator** - 生成工具代码
4. **SkillGenerator** - 生成技能文档
5. **Reviewer** - 审查和修复提案
6. **Solver** - 求解任务
7. **Judge** - 评估答案
8. **Summarizer** - 构建经验卡
9. **SkillRefiner** - 优化技能文本
10. **Planner** - 规划器(已过时)

#### 优点

✅ **清晰的数据契约**
- 使用`@dataclass`明确定义所有结构
- 便于序列化和调试

✅ **完整的验证管道**
- 6层验证(syntax/load/contract/origin/regression/skill)
- 防止坏工具进入生产环境

✅ **模块化的Tool和Skill**
- Tool和Skill分离清晰
- Skill可独立更新

✅ **完整的历史追踪**
- `experiences.jsonl` - 经验记录
- `promotion_log.jsonl` - 晋升日志
- `review_reports.jsonl` - 审查报告

✅ **良好的ReAct Agent设计**
- 严格的Action协议
- 多模态支持(图像+文本)
- 错误恢复机制

#### 主要问题

❌ **过度LLM依赖 (8+ LLM calls/case)**
```
Analyzer → Decider → ToolGenerator → Reviewer →
SkillGenerator → SkillRefiner → (Solver × N)
```
- 成本高昂
- 延迟累积
- 失败点过多

❌ **角色系统过度工程化 (10个角色)**
- 每个角色都有LLM版本 + Mock版本
- 代码重复(payload构造、JSON提取、重试逻辑)
- 维护负担重

❌ **Tool文件过大 (1,500-2,185行/文件)**
- 图像处理逻辑完全内联
- 缺乏模块化和复用
- 难以阅读和维护

❌ **SelfEvolveLoop过于庞大 (519行)**
- 职责过多:
  - 控制流程
  - 数据管理
  - 文件I/O
  - 统计追踪
- 应拆分为多个类

❌ **Skill文本合并逻辑复杂 (80+行)**
- 无标准merge策略
- 基于简单的List去重和文本拼接
- Skill内容可能混乱

❌ **Observation截断丢失信息**
- 中间6000字符被截断
- 可能丢失关键错误信息
- 无智能截断算法

❌ **Tool调用接口繁琐**
```bash
python -m glue_swe.tool_cli mirror_clock_answer_with_restore \
  --args-json '{"image_path":"...","question":"...","enable_vlm":true,...}'
```
- JSON字符串在bash中易错
- 参数太多，Agent容易出错
- 无参数验证

❌ **Skill过于简单，只是"使用手册"**
- 缺少策略性指导
- 缺少组合逻辑
- 缺少失败处理

❌ **缺少跨problem知识转移**
- 每个problem有独立的`learned_assets/`
- 无法复用到其他problem

❌ **无并行化支持**
- 所有角色串行调用
- Tool生成、Skill生成可并行但未实现

---

### 2.2 Autoresearch 深度分析

#### 项目概览
**创建者**: Andrej Karpathy
**核心理念**: 给AI一个真实的LLM训练环境，让它自主进行实验迭代

#### 核心设计

```
autoresearch/
├── prepare.py        # 🔒 固定 - 数据准备 + 工具函数
├── train.py          # ✏️ AI修改 - 模型 + 优化器 + 训练循环
├── program.md        # ✏️ 人工修改 - AI的指令手册
├── results.tsv       # 📊 自动生成 - 实验结果记录
└── pyproject.toml    # 依赖声明
```

#### 三层分工模型

| 层级 | 文件 | 职责 | 可修改性 |
|-----|------|------|---------|
| **数据层** | prepare.py | 数据下载、tokenizer训练、评估度量 | 🔒 固定 |
| **实验层** | train.py | 模型架构、优化器、超参数 | ✏️ AI修改 |
| **指导层** | program.md | 研究方向、循环规则、约束 | ✏️ 人工修改 |

#### 自我进化循环

```
LOOP FOREVER:
  1. 查看git状态
  2. 修改train.py (提出实验想法)
  3. git commit (提交改动)
  4. 运行训练 (5分钟固定预算)
  5. 提取结果 (val_bpb, peak_vram_mb)
  6. 决策:
     - val_bpb改善 → KEEP (保留commit)
     - val_bpb恶化 → DISCARD (git reset)
     - crash → 诊断修复
  7. 记录到results.tsv
  8. 重复
```

#### 关键设计要点

**1. 固定时间预算 (Fixed Time Budget)**
```python
TIME_BUDGET = 300  # 5分钟
```
- ✅ 所有实验可比较
- ✅ 成本可预测(12实验/小时)
- ✅ 自动适应硬件
- ⚠️ 跨硬件不可比

**2. 架构无关评估指标 (Architecture-Agnostic Metric)**
```python
val_bpb = total_nats / (math.log(2) * total_bytes)
# BPB (Bits Per Byte) - 与词表大小无关
```

**3. 最小化作用域 (Minimal Scope)**
- 只有`train.py`可修改
- 无法安装新包
- 无法修改数据处理
- **优势**: 可审查、安全、聚焦

**4. 人机协作 (Human-AI Collaboration)**
- **人类**: 编写`program.md`指导方向
- **AI**: 自动生成和评估想法

**5. 失败即数据 (Failures as Data)**
- `results.tsv`记录keep/discard/crash
- 为后续实验提供反馈

**6. 简单决策 (Simple Decision)**
- 只有2个选择: KEEP or DISCARD
- 基于单一指标(val_bpb)
- 无需复杂的多角色系统

#### 可借鉴的模式

| 模式 | 价值 | 应用场景 |
|------|------|----------|
| **固定预算** | 公平比较，成本可控 | 视觉puzzle的"步数预算" |
| **架构无关指标** | 跨模型可比 | 与tool/skill无关的成功率 |
| **最小作用域** | 安全、可审查 | 只生成必要的tool/skill |
| **人机协作** | 人定方向，AI执行 | program.md指导搜索 |
| **简单决策** | 减少LLM调用 | KEEP/DISCARD，不需要10个角色 |

---

## 3. 当前Agent设计评估

### 是否符合"Skill驱动CLI Agent"模式？

#### ✅ 基本符合

**相似点 (vs Claude Code):**
1. **Agent只用bash** - SWEAgent只接受"bash" action
2. **Skill作为文档** - SKILL.md注入系统提示
3. **Tool作为CLI** - 通过`python -m glue_swe.tool_cli`调用
4. **ReAct循环** - Thought → Action → Observation

#### ⚠️ 但有明显局限

**问题1: Skill层太薄**

当前SKILL.md:
```markdown
## Standard Command
python -m glue_swe.tool_cli mirror_clock_answer_with_restore \
  --args-json '{"image_path":"...", "question":"..."}'
```

只是"使用手册"，缺少:
- ❌ 策略性指导 (何时使用?)
- ❌ 组合逻辑 (多工具如何组合?)
- ❌ 失败处理 (失败了怎么办?)
- ❌ 推理引导 (如何分析图像?)

**应该是:**
```markdown
## When to Use
- Image shows a clock reflected in a mirror
- Question asks about time calculations

## Strategy
1. Inspect image first, estimate current time
2. If unclear → run restore first
3. Then answer with validated time

## Common Failures
- "Could not detect hands" → Try restore with finer step
```

**问题2: Tool调用太繁琐**

每次写这样的命令:
```bash
python -m glue_swe.tool_cli mirror_clock_answer_with_restore \
  --args-json '{"image_path":"/abs/path/...","question":"...","enable_vlm":true}'
```

**问题:**
- JSON字符串在bash中易错(引号转义)
- 参数太多，Agent容易漏掉
- 无参数验证

**建议简化:**
```bash
python -m glue_swe.tools mirror_clock answer <image> "<question>"
python -m glue_swe.tools mirror_clock restore <image>
```

**问题3: 缺少Skill层次结构**

当前:
```
Skill (SKILL.md)
  ↓
Tool (tool_cli)
```

**应该有:**
```
High-Level Skill (solve_mirror_clock_puzzle)
  ↓ 组合
Mid-Level Skill (restore_then_answer)
  ↓ 调用
Low-Level Tool (restore, answer)
```

**问题4: Tool输出难以解析**

Skill说:
```markdown
## Output Parsing
- Preferred: `payload.answer`
- Fallback: `payload.final_answer_computed`
```

要求Agent:
1. 解析JSON字符串
2. 导航嵌套字段
3. 处理fallback逻辑

**太复杂!** 应该:
```bash
# Tool直接输出答案
ANSWER: 3:45
STATUS: ok
```

### 对比表

| 维度 | 当前设计 | Claude Code | 理想设计 |
|------|----------|-------------|----------|
| **Agent核心** | ✅ ReAct + bash | ✅ ReAct + 多tool | ✅ ReAct + bash |
| **Skill形式** | ⚠️ 简单文档 | ✅ 策略文档 | ✅ 分层策略 |
| **Skill层次** | ❌ 单层 | ✅ 可嵌套 | ✅ 3层(策略/组合/工具) |
| **Tool调用** | ⚠️ 繁琐CLI | ✅ 简洁接口 | ✅ 统一CLI |
| **输出解析** | ❌ 复杂JSON | ✅ 标准化 | ✅ 简单格式 |
| **动态Skill** | ❌ 静态预加载 | ✅ 动态发现 | ✅ 可生成 |

---

## 4. 重新设计方案

### 4.1 设计原则

基于对两个项目的分析和当前agent的评估，新设计遵循:

**从autoresearch借鉴:**
1. ✅ **固定预算** - 每次尝试固定步数(如20步)
2. ✅ **最小作用域** - 只生成必要的文件
3. ✅ **简单决策** - KEEP/DISCARD，不需要10个角色
4. ✅ **人机协作** - `program.md`指导搜索方向
5. ✅ **失败即数据** - 记录所有尝试

**从Glue_SWE保留:**
1. ✅ **VLM Agent核心** - ReAct循环很好
2. ✅ **Tool/Skill分离** - 但需增强
3. ✅ **验证流程** - 但减少层级(3层足够)
4. ✅ **能力存储** - 但简化结构

**核心创新:**
1. 🆕 **单例聚焦** - 一次只解决一个puzzle
2. 🆕 **减少LLM调用** - 2-3个LLM calls/迭代
3. 🆕 **Tool优先** - 先生成可验证的tool
4. 🆕 **渐进式改进** - 从简单开始
5. 🆕 **Skill增强** - 策略性文档，分层结构

### 4.2 新架构设计

```
vision_agent_evolve/
├── core/                       # Agent引擎
│   ├── agent.py               # VLM ReAct agent (保留原设计)
│   ├── vlm_client.py          # OpenAI兼容客户端
│   ├── types.py               # 数据契约
│   └── parser.py              # 响应解析
│
├── skills/                     # Skill系统 (增强版)
│   ├── base.py                # Skill基类
│   ├── loader.py              # 动态发现和加载
│   ├── renderer.py            # 渲染到系统提示
│   └── library/               # Skill库
│       ├── foundation/        # 基础技能
│       │   ├── vision_analysis.md
│       │   └── reasoning.md
│       ├── mirror_clock/      # 任务特定技能
│       │   ├── SKILL.md
│       │   └── references/
│       └── defuse_bomb/
│
├── tools/                      # Tool系统 (简化版)
│   ├── __main__.py            # 统一CLI入口
│   ├── base.py                # Tool基类
│   ├── registry.py            # 简化的注册
│   ├── cli_builder.py         # CLI包装器
│   └── implementations/       # Tool实现(模块化)
│       ├── mirror_clock/
│       │   ├── restore.py     (~150行)
│       │   ├── answer.py      (~150行)
│       │   ├── cv_utils.py    (共享CV逻辑)
│       │   └── README.md      (工具说明)
│       ├── defuse_bomb/
│       │   ├── solve.py       (~200行)
│       │   ├── cv_utils.py
│       │   └── vlm_utils.py
│       └── shared/
│           ├── image_proc.py  (通用图像处理)
│           └── geometry.py    (几何计算)
│
├── evolution/                  # 自我进化 (大幅简化)
│   ├── loop.py                # 主循环 (~200行, vs 519行)
│   ├── roles.py               # 合并的角色 (~200行)
│   │   ├── AnalyzerDecider   (分析+决策，1个LLM call)
│   │   └── Generator         (生成tool/skill，1个LLM call)
│   ├── validator.py           # 验证引擎 (~100行)
│   ├── store.py               # 能力存储 (~150行)
│   └── types.py               # 数据契约
│
├── datasets/                   # 数据集
│   └── mira/                  # MIRA puzzle数据集
│       ├── examples/
│       └── metadata.json
│
├── learned/                    # 学到的能力
│   ├── tools/                 # 生成的工具
│   │   ├── tool_xyz.py
│   │   └── manifests/
│   └── skills/                # 生成的技能
│       ├── skill_xyz.md
│       └── manifests/
│
├── program.md                  # 人工指导文档 (可编辑)
├── evolution_log.jsonl        # 进化历史
├── run.py                      # 主入口
├── pyproject.toml             # 依赖
└── README.md                   # 项目文档
```

### 4.3 核心改变说明

#### 改变1: 简化角色系统 (10个 → 2个)

**原系统 (10个角色, 8+ LLM calls):**
```
Analyzer → Decider → ToolGenerator → SkillGenerator →
Reviewer → Solver → Judge → Summarizer → SkillRefiner
```

**新系统 (2个角色, 2-3 LLM calls):**

**角色1: AnalyzerDecider** (1 LLM call)
- 输入: case, attempt, evaluation
- 输出: FailureAnalysis + Decision
- 职责:
  - 分析失败原因
  - 决定下一步(generate_tool / generate_skill / both / give_up)

**角色2: Generator** (1 LLM call for tool, 1 for skill if needed)
- 输入: FailureAnalysis, Decision
- 输出: ToolProposal or SkillProposal
- 职责:
  - 生成工具代码
  - 生成技能文档
  - 内置基本的自我修复

**移除的角色:**
- ❌ Reviewer (Generator内置基本检查)
- ❌ Summarizer (简化为统计记录)
- ❌ SkillRefiner (手动或后期优化)
- ❌ Planner (已过时)

#### 改变2: 增强Skill系统

**原Skill (使用手册):**
```markdown
---
name: mirror_clock
description: "Solve mirror_clock tasks through CLI tools only."
---

## Standard Command
python -m glue_swe.tool_cli mirror_clock_answer_with_restore \
  --args-json '{"image_path":"...","question":"..."}'
```

**新Skill (策略文档):**
```markdown
---
name: mirror_clock_solver
description: "Multi-step strategy for mirror clock puzzles"
level: high
depends_on: [vision_analysis]
---

# Mirror Clock Solver

## When to Use
- Image contains a clock reflected in a mirror
- Question asks about time or time calculations
- Question mentions "mirror" or shows reversed image

## Prerequisites
- Run `vision_analysis` skill first to understand image

## Strategy

### Step 1: Inspect Image
Look at the image and answer:
- Is this clearly a mirrored clock?
- Can you estimate the time shown?
- Are the hands clearly visible?

### Step 2: Decide Approach
- **If hands clear**: Proceed to Step 3
- **If hands unclear**: First restore the clock
  ```bash
  python -m glue_swe.tools mirror_clock restore <image_path>
  ```
  This will save restored_clock.png in working directory.

### Step 3: Answer Question
```bash
python -m glue_swe.tools mirror_clock answer <image_path> "<question>"
```

**Output format:**
```
ANSWER: HH:MM
STATUS: ok
ARTIFACTS: restored_clock.png
```

### Step 4: Validate
- Check answer is in HH:MM format
- Verify answer makes sense (0-23 hours, 0-59 minutes)

## Common Failures & Solutions

| Failure | Reason | Solution |
|---------|--------|----------|
| "Could not detect hands" | Image too blurry | Try restore with --fine-step |
| "Ambiguous time" | Question unclear | Parse question more carefully |
| "Invalid format" | Tool error | Check image path is absolute |

## Example

Task: "This is what a clock looks like in a mirror. What time will it be in 1 hours and 40 minutes?"

1. Inspect image → see mirrored clock showing ~2:30
2. Run restore → get clear image
3. Run answer → get "4:10"
4. Validate → correct format ✓

## Tips
- Always use absolute paths for images
- Quote the question string
- Check STATUS before using ANSWER
```

**新Skill特点:**
- ✅ 分层结构 (high/mid/low level)
- ✅ 依赖声明 (`depends_on`)
- ✅ 何时使用 (When to Use)
- ✅ 多步策略 (Strategy)
- ✅ 失败处理 (Common Failures)
- ✅ 完整示例 (Example)

#### 改变3: 简化Tool CLI

**原调用:**
```bash
python -m glue_swe.tool_cli mirror_clock_answer_with_restore \
  --args-json '{"image_path":"/abs/path/image.png","question":"What time?","enable_vlm":true,"save_debug":true,"output_prefix":"mirror_clock"}' \
  --run-dir "/abs/path/to/run_dir" \
  --step 1
```

**新调用:**
```bash
# 统一入口
python -m glue_swe.tools mirror_clock answer <image> "<question>"
python -m glue_swe.tools mirror_clock restore <image>
python -m glue_swe.tools defuse_bomb solve <image>

# 高级选项
python -m glue_swe.tools mirror_clock answer <image> "<q>" --vlm --debug
```

**实现:**
```python
# tools/__main__.py
import sys
from pathlib import Path

def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage: python -m glue_swe.tools <tool_name> <subcommand> [args...]")
        sys.exit(1)

    tool_name = args[0]
    subcommand = args[1]

    if tool_name == "mirror_clock":
        from .implementations.mirror_clock import cli
        cli.run(subcommand, args[2:])
    elif tool_name == "defuse_bomb":
        from .implementations.defuse_bomb import cli
        cli.run(subcommand, args[2:])
    # ...
```

**输出标准化:**
```
ANSWER: <value>
STATUS: ok | error
ARTIFACTS: file1.png, file2.json
---
[Optional debug info or error message]
```

#### 改变4: 简化Evolution Loop

**原循环 (519行):**
- 职责混乱: 流程控制 + I/O + 统计
- 10个角色调用
- 复杂的强制生成逻辑

**新循环 (~200行):**

```python
class EvolutionLoop:
    def __init__(self, config, store, validator):
        self.config = config
        self.store = store
        self.validator = validator
        self.analyzer_decider = AnalyzerDecider(...)
        self.generator = Generator(...)

    def run_single_case(self, case: TaskCase) -> bool:
        """聚焦单个case直到成功或达到max_attempts"""

        for attempt_num in range(self.config.max_attempts):
            # 1. 尝试解决 (使用当前能力)
            result = self._solve_case(case)

            if result.success:
                log_success(case, attempt_num)
                return True  # ✅ 成功，退出

            # 2. 分析失败 + 决策 (1 LLM call)
            analysis_decision = self.analyzer_decider.analyze_and_decide(
                case=case,
                result=result,
                current_capabilities=self.store.list_capabilities()
            )

            if analysis_decision.action == "give_up":
                log_give_up(case, analysis_decision.reason)
                return False  # ❌ 放弃

            # 3. 生成能力 (1-2 LLM calls)
            proposals = self.generator.generate(analysis_decision)

            # 4. 验证
            validation = self.validator.validate(
                proposals,
                origin_case=case,
                regression_cases=self.store.get_solved_cases()
            )

            # 5. 决策: KEEP or DISCARD
            if validation.passed:
                self.store.promote(proposals)
                log_keep(proposals, validation)
            else:
                log_discard(proposals, validation)

            # 6. 继续下一轮尝试

        return False  # 达到max_attempts
```

**特点:**
- ✅ 单一职责: 控制进化流程
- ✅ 简单决策: KEEP/DISCARD
- ✅ 聚焦单例: 直到成功或放弃
- ✅ 2-3 LLM calls/iteration

#### 改变5: 模块化Tool实现

**原结构 (单文件巨型):**
```
tools/defuse_bomb_hybrid/tool.py  (1,626行)
  - CV处理逻辑
  - VLM调用逻辑
  - 主工具类
  - 辅助函数
  - 全部混在一起
```

**新结构 (模块化):**
```
tools/implementations/defuse_bomb/
├── solve.py           (~200行) - 主工具
├── cv_utils.py        (~150行) - CV处理
├── vlm_utils.py       (~100行) - VLM调用
├── cli.py             (~50行)  - CLI包装
└── README.md          - 工具文档

tools/implementations/shared/
├── image_proc.py      - 通用图像处理
├── geometry.py        - 几何计算
└── vlm_client.py      - VLM客户端封装
```

**优势:**
- ✅ 代码复用 (`shared/`)
- ✅ 易于测试 (每个模块独立)
- ✅ 易于阅读 (<200行/文件)
- ✅ 易于生成 (LLM生成小文件更可靠)

#### 改变6: 验证流程简化

**原验证 (6层):**
1. syntax_ok - AST parse
2. load_ok - import test
3. contract_ok - manifest check
4. origin_case_ok - 解决原case?
5. regression_ok - 不破坏已解决case?
6. skill_ok - 文档有效?

**新验证 (3层):**

```python
class Validator:
    def validate(self, proposals, origin_case, regression_cases):
        results = ValidationResult()

        # 1. 静态检查 (syntax + basic load)
        results.static_ok = self._check_syntax_and_load(proposals.tool)
        if not results.static_ok:
            results.reason = "Syntax or import error"
            return results

        # 2. Origin case检查 (最关键)
        results.origin_ok = self._test_on_case(origin_case, proposals)
        if not results.origin_ok:
            results.reason = "Does not solve origin case"
            return results

        # 3. Regression检查 (optional, 如果有已解决case)
        if regression_cases:
            results.regression_ok = self._test_regression(
                regression_cases, proposals
            )
            if not results.regression_ok:
                results.reason = f"Breaks {results.failed_cases} solved cases"
                return results

        results.passed = True
        return results
```

**简化理由:**
- ❌ `contract_ok` - 合并到`static_ok`
- ❌ `skill_ok` - Skill是文档，无需运行时验证
- ✅ 保留核心: syntax, origin, regression

### 4.4 进化策略

#### 单例聚焦模式 (vs 批量模式)

**原模式 (Glue_SWE):**
```python
for case in all_failed_cases:
    try_to_improve(case)  # 每个case尝试1次
    # 可能生成能力但没解决任何case
```

**新模式 (Vision Agent Evolve):**
```python
for case in dataset:
    while not solved and attempts < max_attempts:
        try_to_solve(case)
        if failed:
            generate_capability()
            validate()
            retry()
    # 确保这个case被解决再继续下一个
```

**优势:**
- ✅ 确保每个case被深度探索
- ✅ 避免浅尝辄止
- ✅ 学到的能力更有针对性

#### 能力复用策略

```
Case 1 (mirror_clock_1):
  → 学到: mirror_clock_restore_tool
  → 学到: mirror_clock_answer_tool
  → 学到: mirror_clock_solver_skill

Case 2 (mirror_clock_2):
  → 复用: mirror_clock_solver_skill ✓
  → 需要: mirror_clock_multi_question_skill (新)
  → 学到: mirror_clock_multi_question_skill

Case 3 (defuse_bomb_1):
  → 学到: defuse_bomb_cv_tool
  → 学到: defuse_bomb_solver_skill
```

**跨case知识转移:**
- 同类任务共享tool/skill
- 复用`shared/`中的通用模块
- Skill可组合 (`depends_on`)

### 4.5 Human Guidance (program.md)

```markdown
# Vision Agent Evolution - Program

## Mission
Solve vision puzzles by autonomously generating tools and skills.

## Current Focus
- Dataset: MIRA puzzles
- Priority: Mirror clock problems first, then bomb defusal

## Strategy Guidelines

### Tool Generation
- **Prefer simple over complex**: 50-line tool > 500-line tool
- **Reuse shared modules**: Use `tools/implementations/shared/`
- **CV first, VLM second**: Try CV-only before VLM
- **Test before commit**: Must pass origin_case_ok

### Skill Generation
- **Be specific**: Describe exact steps, not vague advice
- **Include failure modes**: Common errors and solutions
- **Show examples**: Include 1-2 concrete examples
- **Layer skills**: High-level strategy → Mid-level tactic → Low-level tool

### When to Give Up
- After 10 failed attempts on same case
- If validation never passes (syntax errors persist)
- If the case requires external knowledge not in image

## Constraints
- **Code size**: Tools <200 lines, Skills <100 lines
- **LLM calls**: Max 3 per iteration
- **Time budget**: 20 agent steps per attempt
- **Memory**: Keep <5 variants of same tool

## Success Metrics
- Solve rate: >80% of dataset
- Iterations to solve: <5 avg
- Tool reuse: >50% of tools used in 2+ cases
- Code bloat: <2000 total lines in learned/

## Notes
(Editable by human - add observations, adjust strategy)

- 2026-03-13: Started with mirror_clock dataset
- 2026-03-13: Noticed CV-only approach works for 60% cases
```

**使用方式:**
- Human定期更新策略
- AnalyzerDecider读取program.md
- Generator遵循约束

### 4.6 对比总结

| 维度 | Glue_SWE | Vision Agent Evolve | 改进幅度 |
|------|----------|---------------------|---------|
| **代码量** | ~10,000行 | ~2,000行 (目标) | -80% |
| **LLM calls/迭代** | 8+ | 2-3 | -70% |
| **角色数量** | 10 | 2 | -80% |
| **最大文件** | 519行(loop) 2,185行(tool) | 200行 | -60%/-90% |
| **验证层级** | 6层 | 3层 | -50% |
| **Tool调用** | 繁琐JSON CLI | 简洁统一CLI | ++ |
| **Skill质量** | 使用手册 | 策略文档 | ++ |
| **聚焦模式** | 批量处理 | 单例聚焦 | ++ |
| **模块化** | 单文件巨型 | 多文件模块化 | ++ |

---

## 5. 实施计划

### Phase 1: 核心框架 (Day 1-2)

**目标**: 建立基本工作的agent系统

**任务:**
1. ✅ 创建项目结构
2. ✅ 迁移`core/agent.py` (保留原ReAct设计)
3. ✅ 实现`core/vlm_client.py`
4. ✅ 定义`core/types.py` (数据契约)
5. ✅ 实现简化的`tools/registry.py`
6. ✅ 创建统一CLI入口 `tools/__main__.py`

**验证:**
- 可运行基本ReAct agent
- 可通过CLI调用预定义工具
- 工具输出标准化格式

### Phase 2: Tool实现模块化 (Day 3-4)

**目标**: 拆分和重构现有工具

**任务:**
1. ✅ 创建`tools/implementations/shared/`
   - `image_proc.py` (通用图像处理)
   - `geometry.py` (几何计算)
   - `vlm_client.py` (VLM调用)
2. ✅ 重构`mirror_clock`工具
   - 拆分为`restore.py` + `answer.py`
   - 提取共享逻辑到`shared/`
3. ✅ 重构`defuse_bomb`工具
   - 拆分为`solve.py` + `cv_utils.py`
4. ✅ 实现CLI包装器

**验证:**
- 所有工具文件<200行
- 可通过新CLI调用
- 输出标准化格式
- 通过原有测试案例

### Phase 3: Skill系统增强 (Day 5-6)

**目标**: 创建策略性Skill文档

**任务:**
1. ✅ 实现`skills/base.py` (Skill基类)
2. ✅ 实现`skills/loader.py` (动态加载)
3. ✅ 创建基础Skill库
   - `foundation/vision_analysis.md`
   - `foundation/reasoning.md`
4. ✅ 改写现有Skill为策略文档
   - `mirror_clock/SKILL.md` (增强版)
   - `defuse_bomb/SKILL.md` (增强版)
5. ✅ 实现Skill依赖解析

**验证:**
- Skill可声明依赖
- Skill包含完整策略
- Skill包含失败处理
- Agent能正确使用Skill

### Phase 4: 进化循环实现 (Day 7-9)

**目标**: 实现自我进化核心

**任务:**
1. ✅ 定义`evolution/types.py`
   - `FailureAnalysis`
   - `Decision`
   - `ToolProposal`
   - `SkillProposal`
   - `ValidationResult`
2. ✅ 实现`evolution/roles.py`
   - `AnalyzerDecider` (合并角色)
   - `Generator` (Tool/Skill生成)
3. ✅ 实现`evolution/validator.py`
   - 3层验证逻辑
4. ✅ 实现`evolution/store.py`
   - 简化的能力存储
5. ✅ 实现`evolution/loop.py`
   - 单例聚焦循环

**验证:**
- 可在单个case上循环
- 可生成tool/skill
- 验证流程正确
- KEEP/DISCARD决策正确

### Phase 5: 数据集和测试 (Day 10-11)

**目标**: 准备MIRA数据集和测试

**任务:**
1. ✅ 准备`datasets/mira/`
2. ✅ 创建数据加载器
3. ✅ 实现评估脚本
4. ✅ 编写单元测试
5. ✅ 编写集成测试

**验证:**
- 可加载MIRA数据集
- 可运行完整进化循环
- 测试覆盖核心逻辑

### Phase 6: Program.md和文档 (Day 12)

**目标**: 完善人工指导和文档

**任务:**
1. ✅ 编写`program.md` (人工指导)
2. ✅ 完善`README.md`
3. ✅ 编写Tool/Skill开发指南
4. ✅ 添加示例用法

**验证:**
- 文档完整清晰
- 示例可运行
- 他人可上手

### Phase 7: 实验和优化 (Day 13-14)

**目标**: 在真实数据上测试和优化

**任务:**
1. ✅ 运行MIRA数据集实验
2. ✅ 收集成功/失败案例
3. ✅ 分析瓶颈
4. ✅ 优化prompts
5. ✅ 优化验证逻辑

**验证:**
- 解决率>60%
- 平均迭代数<10
- 无明显卡住的case

---

## 6. 预期成果

### 定量指标

| 指标 | 目标 | 对比Glue_SWE |
|------|------|--------------|
| **代码总量** | <2,500行 | -75% |
| **LLM调用/case** | 2-3 × 迭代数 | -70% |
| **平均迭代到成功** | <10 | N/A (新指标) |
| **工具复用率** | >50% | N/A (新指标) |
| **解决率** | >70% | (待对比) |
| **单文件最大行数** | <200 | -60%/-90% |

### 定性改进

✅ **代码可读性**
- 文件小且聚焦
- 模块化清晰
- 注释充分

✅ **可维护性**
- 角色简单(2个)
- 循环逻辑清晰
- 依赖明确

✅ **可扩展性**
- 易添加新tool
- 易添加新skill
- 易调整策略

✅ **可调试性**
- 完整日志
- 清晰的失败追踪
- 可重现的实验

✅ **用户体验**
- 简洁的CLI
- 清晰的输出
- 完善的文档

---

## 7. 风险和缓解

### 风险1: Tool生成质量低

**风险**: LLM生成的工具代码可能有bug

**缓解:**
- ✅ 3层验证(syntax/origin/regression)
- ✅ 提供`shared/`模块减少从零生成
- ✅ 提供Tool模板
- ✅ Generator内置基本修复

### 风险2: Skill策略不足

**风险**: 生成的Skill可能还是太简单

**缓解:**
- ✅ 提供详细的Skill模板
- ✅ 在prompt中强调策略性
- ✅ 手动优化初始Skill库
- ✅ 可人工编辑生成的Skill

### 风险3: 单例聚焦陷入死循环

**风险**: 某个case可能永远解决不了

**缓解:**
- ✅ `max_attempts`限制
- ✅ `give_up`决策选项
- ✅ 记录失败原因
- ✅ 人工可介入

### 风险4: 验证不充分

**风险**: 坏工具通过验证

**缓解:**
- ✅ `origin_case_ok`是硬性要求
- ✅ `regression_ok`防止破坏
- ✅ 可扩展验证规则
- ✅ 人工可审查promoted/

### 风险5: LLM成本过高

**风险**: 即使减少到2-3 calls，成本仍可能高

**缓解:**
- ✅ 固定迭代预算(如20步)
- ✅ 使用更小的模型(Haiku for generation?)
- ✅ 缓存和复用分析结果
- ✅ 提前放弃无望的case

---

## 8. 未来扩展方向

### 短期 (1-2个月)

1. **跨任务知识转移**
   - 从mirror_clock学到的技能应用到其他时钟问题
   - 从defuse_bomb学到的CV技术应用到其他视觉puzzle

2. **Skill组合引擎**
   - 自动组合多个Skill
   - 学习Skill组合模式

3. **Tool参数自动调优**
   - 学习每个工具的最佳参数
   - 基于历史成功案例推荐参数

### 中期 (3-6个月)

1. **多模态扩展**
   - 支持视频puzzle
   - 支持音频+视觉组合

2. **并行化探索**
   - 同时尝试多个tool/skill方向
   - 并行验证候选

3. **元学习**
   - 学习"什么类型的改动有效"
   - 优先尝试高成功率的策略

### 长期 (6-12个月)

1. **自我改进架构**
   - Agent可修改evolution loop逻辑
   - Agent可优化自己的prompts

2. **知识蒸馏**
   - 将学到的能力蒸馏到更小的模型
   - 减少运行时LLM依赖

3. **社区能力库**
   - 分享学到的tool/skill
   - 从社区导入验证过的能力

---

## 9. 总结

### 核心洞察

1. **简单比复杂好**
   - 2个角色 > 10个角色
   - 200行 > 2000行
   - KEEP/DISCARD > 复杂的多阶段决策

2. **聚焦比广撒网好**
   - 单例深度探索 > 多例浅尝辄止
   - 确保成功再继续 > 快速失败快速放弃

3. **策略比手册重要**
   - Skill应该教"为什么" > 仅教"怎么做"
   - 失败处理是Skill的核心部分

4. **模块化带来灵活性**
   - 小文件易生成、易测试、易维护
   - 共享模块减少重复和错误

5. **人机协作最有效**
   - 人定方向(program.md)
   - AI执行探索
   - 人审查和调整

### 成功标准

项目成功的标志:
- ✅ 在单个MIRA例子上可自主迭代到成功
- ✅ 生成的tool可复用到其他例子
- ✅ 代码量<2,500行但功能完整
- ✅ 其他研究者可理解和扩展
- ✅ 可应用到新的视觉puzzle数据集

---

## 附录A: 参考文献

- **Glue_SWE项目**: `/Users/macbook/Desktop/exp_ali/Glue_SWE/Glue_SWE/`
- **Autoresearch项目**: `/Users/macbook/Desktop/exp_ali/Glue_SWE/autoresearch/`
- **ReAct论文**: Yao et al. 2022, "ReAct: Synergizing Reasoning and Acting in Language Models"
- **Claude Code文档**: https://docs.anthropic.com/claude-code

## 附录B: 术语表

- **ReAct**: Reasoning + Acting循环模式
- **Skill**: 策略性文档，指导agent如何行动
- **Tool**: 可执行代码，完成具体操作
- **Origin Case**: 触发能力生成的原始失败case
- **Regression**: 新能力破坏了已解决的case
- **KEEP**: 保留生成的能力
- **DISCARD**: 丢弃生成的能力
- **BPB**: Bits Per Byte，架构无关的评估指标
- **Fixed Budget**: 固定时间/步数预算

---

**文档版本**: 1.0
**最后更新**: 2026-03-13
**下一步**: 开始Phase 1实施
