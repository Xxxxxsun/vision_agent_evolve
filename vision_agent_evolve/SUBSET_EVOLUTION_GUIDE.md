# Subset隔离演化 + Token追踪指南

## ✅ 已实现的功能

### 1️⃣ Subset隔离演化

每个问题集合（subset）独立演化，互不干扰，只从foundation开始。

### 2️⃣ 实时Token使用追踪

显示每次LLM调用的token消耗和累积总量。

---

## 🎯 使用方法

### 基本用法

```bash
# Subset 1: 镜像时钟问题集
python run.py \
  --mode evolve \
  --subset mirror_clock \
  --example datasets/mira/mirror_clock_001.json \
  --max-attempts 10

# Subset 2: 炸弹拆除问题集
python run.py \
  --mode evolve \
  --subset defuse_bomb \
  --example datasets/mira/defuse_bomb_001.json \
  --max-attempts 10

# Subset 3: 其他问题
python run.py \
  --mode evolve \
  --subset puzzle_type_x \
  --example datasets/mira/puzzle_x_001.json
```

### 不使用subset（所有问题共享learned）

```bash
python run.py \
  --mode evolve \
  --example datasets/mira/example_001.json
  # 不指定--subset，learned目录为 learned/
```

---

## 📂 目录结构

### Subset隔离模式

```
vision_agent_evolve/
├── learned/
│   ├── mirror_clock/          ← Subset 1的learned内容
│   │   ├── tools/
│   │   │   ├── mirror_restore.py
│   │   │   └── rotate_correct.py
│   │   ├── skills/
│   │   │   └── mirror_clock_solver/
│   │   └── evolution_log.jsonl
│   │
│   ├── defuse_bomb/           ← Subset 2的learned内容
│   │   ├── tools/
│   │   │   └── wire_extractor.py
│   │   ├── skills/
│   │   │   └── bomb_solver/
│   │   └── evolution_log.jsonl
│   │
│   └── puzzle_type_x/         ← Subset 3的learned内容
│       └── ...
│
└── skills/library/
    └── foundation/            ← 所有subset共享的foundation
        ├── vision_analysis.md
        ├── reasoning.md
        └── try_direct_first.md
```

### 无Subset模式

```
learned/
├── tools/                     ← 所有问题共享
├── skills/                    ← 所有问题共享
└── evolution_log.jsonl
```

---

## 🔍 初始状态

### 每个Subset开始时

```
✅ Foundation Skills (共享):
  - vision_analysis.md
  - reasoning.md
  - try_direct_first.md

❌ Learned Tools: 无（空目录）
❌ Learned Skills: 无（空目录）
❌ Task-specific预置: 无（已删除）
```

**结果**: 真正的从零演化！

---

## 💡 实时Token追踪

### 控制台输出示例

```bash
--- Attempt 3/10 ---
Solving with current capabilities...
✗ Failed. Answer: 10:30 (expected: 02:30)
  Artifacts generated: 1
    - artifacts/restored_clock.png

Analyzing failure with visual context...
  → Original image: datasets/mira/images/mirror_clock_001.png
  → Processing 1 artifact images for analysis
  [AnalyzerDecider] Tokens: 3,247 (prompt: 2,891, completion: 356)

Analysis: VLM cannot interpret mirrored clock
Next action: generate_tool

Generating tool...
  [Generator/Tool] Tokens: 1,892 (prompt: 645, completion: 1,247)
Generated: mirror_restore

Validating tool...
✓ Validation passed! Promoting tool...

--- Attempt 4/10 ---
...

✓ SOLVED! Answer: 02:30

============================================================
Token Usage Summary (after 4 attempts)
============================================================
AnalyzerDecider: 9,834 tokens
  - Prompt: 8,123
  - Completion: 1,711
Generator: 5,678 tokens
  - Prompt: 2,034
  - Completion: 3,644
============================================================
TOTAL: 15,512 tokens
  - Prompt: 10,157
  - Completion: 5,355
============================================================
```

### Token追踪细节

**每次LLM调用显示**:
```
[AnalyzerDecider] Tokens: 3,247 (prompt: 2,891, completion: 356)
[Generator/Tool] Tokens: 1,892 (prompt: 645, completion: 1,247)
[Generator/Skill] Tokens: 1,234 (prompt: 567, completion: 667)
```

**最终总结**:
- 分角色统计（AnalyzerDecider vs Generator）
- 分类型统计（Prompt vs Completion）
- 总计

---

## 🧪 实验场景

### 场景1: 对比不同subset的学习效率

```bash
# Subset A: 镜像时钟（10个例子）
for i in {1..10}; do
  python run.py --mode evolve --subset mirror_clock \
    --example datasets/mira/mirror_clock_00$i.json
done

# Subset B: 炸弹拆除（10个例子）
for i in {1..10}; do
  python run.py --mode evolve --subset defuse_bomb \
    --example datasets/mira/defuse_bomb_00$i.json
done

# 对比：
# - learned/mirror_clock/ vs learned/defuse_bomb/
# - Token使用量
# - 迭代次数
# - 工具复用率
```

### 场景2: 知识累积观察

```bash
# 第1个例子（简单镜像）
python run.py --mode evolve --subset test \
  --example example_001.json

# 查看生成了什么
ls learned/test/tools/
ls learned/test/skills/

# 第2个例子（镜像+旋转）
python run.py --mode evolve --subset test \
  --example example_002.json

# 查看是否复用了第1个的工具
cat learned/test/evolution_log.jsonl
```

### 场景3: Token成本分析

```bash
# 记录每个例子的token使用
python run.py --mode evolve --subset experiment \
  --example example_001.json 2>&1 | tee log_001.txt

# 提取token总量
grep "TOTAL:" log_001.txt

# 分析趋势：是否随着learned能力增加，token消耗减少？
```

---

## 📊 数据收集

### Evolution Log格式

`learned/<subset>/evolution_log.jsonl`:

```jsonl
{"case_id": "mirror_001", "solve_success": true, "attempts": 3}
{"iteration": 1, "case_id": "mirror_001", "tool_generated": "mirror_restore", "decision": "keep"}
{"iteration": 2, "case_id": "mirror_001", "skill_generated": "mirror_solver", "decision": "keep"}
...
```

### Token统计脚本

```bash
# 统计某个subset的总token消耗
grep "TOTAL:" learned/mirror_clock/*.log | \
  awk '{sum+=$2} END {print "Total tokens:", sum}'
```

---

## 🎯 核心优势

### 1. 隔离演化

| 特性 | 无Subset | 有Subset |
|------|---------|---------|
| **独立性** | 所有问题混在一起 | 每个问题集独立 |
| **实验对照** | 难以对比 | 可对照实验 |
| **知识污染** | A的工具影响B | 完全隔离 |
| **复现性** | 难以复现 | 易于复现 |

### 2. Foundation Only

| 内容 | 是否保留 | 原因 |
|------|---------|------|
| vision_analysis | ✅ 保留 | 通用视觉分析策略 |
| reasoning | ✅ 保留 | 通用推理框架 |
| try_direct_first | ✅ 保留 | 引导VLM先尝试 |
| mirror_clock skill | ❌ 删除 | 任务特定，应该自己学 |
| mirror_clock tools | ❌ 删除 | 任务特定，应该自己生成 |

### 3. Token可见性

**实时反馈**:
- 看到每次调用的消耗
- 识别哪个角色消耗更多
- 发现异常的高消耗调用

**事后分析**:
- 总结一个case的总成本
- 对比不同案例的效率
- 优化prompt以降低成本

---

## 💡 使用建议

### 实验设计

```bash
# 1. 定义subset
SUBSET="mirror_clock_experiment_v1"

# 2. 准备例子集合
EXAMPLES=(
  "datasets/mira/mirror_001.json"  # 简单镜像
  "datasets/mira/mirror_002.json"  # 镜像+旋转
  "datasets/mira/mirror_003.json"  # 镜像+模糊
)

# 3. 逐个运行
for ex in "${EXAMPLES[@]}"; do
  echo "Running $ex..."
  python run.py --mode evolve --subset $SUBSET --example $ex
  echo "---"
done

# 4. 分析结果
echo "Learned tools:"
ls learned/$SUBSET/tools/

echo "Learned skills:"
ls learned/$SUBSET/skills/

echo "Evolution log:"
cat learned/$SUBSET/evolution_log.jsonl | jq
```

### 成本控制

```bash
# 设置较小的max-attempts避免过度消耗
python run.py --mode evolve --subset test \
  --example xxx.json \
  --max-attempts 5  # 限制为5次，不是10次
```

### 清理和重启

```bash
# 清空某个subset，重新开始
rm -rf learned/mirror_clock/

# 重新演化
python run.py --mode evolve --subset mirror_clock --example xxx.json
```

---

## 📈 预期输出示例

### 完整运行输出

```
=== Vision Agent Self-Evolution ===

Case: mirror_clock_001
Task: What time is shown on this mirror clock?
Max attempts: 10
Subset: mirror_clock (isolated evolution)
Learned directory: learned/mirror_clock/

============================================================
Evolution Loop: mirror_clock_001
Subset: mirror_clock
Learned Dir: /path/to/learned/mirror_clock
Task: What time is shown on this mirror clock?
============================================================

--- Attempt 1/10 ---
Solving with current capabilities...
✗ Failed. Answer: 10:30 (expected: 02:30)

Analyzing failure with visual context...
  → Original image: datasets/mira/images/mirror_clock_001.png
  [AnalyzerDecider] Tokens: 3,247 (prompt: 2,891, completion: 356)

Analysis: VLM sees mirrored clock, reads wrong
Next action: generate_tool

Generating tool...
  [Generator/Tool] Tokens: 1,892 (prompt: 645, completion: 1,247)
Generated: mirror_restore

Validating tool...
✓ Validation passed! Promoting tool...

--- Attempt 2/10 ---
Solving with current capabilities...
✓ SOLVED! Answer: 02:30

============================================================
Token Usage Summary (after 2 attempts)
============================================================
AnalyzerDecider: 3,247 tokens
  - Prompt: 2,891
  - Completion: 356
Generator: 1,892 tokens
  - Prompt: 645
  - Completion: 1,247
============================================================
TOTAL: 5,139 tokens
  - Prompt: 3,536
  - Completion: 1,603
============================================================

✓✓✓ SUCCESS! Case solved. ✓✓✓
```

---

## 🎉 总结

现在系统完全支持：

✅ **Subset隔离**: 每个问题集独立演化
✅ **Foundation Only**: 只从基础skill开始
✅ **实时Token追踪**: 每次调用都可见
✅ **成本统计**: 最终总结显示总消耗
✅ **真正的自我进化**: 从零学习，不依赖预置

**你的实验需求完全满足！** 🚀
