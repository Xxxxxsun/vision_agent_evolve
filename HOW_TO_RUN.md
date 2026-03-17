# Vision Agent Evolve - 如何运行

## 🎉 项目完成！

新项目已创建在: `vision_agent_evolve/`

**项目统计**:
- 📊 总代码量: ~3000行 (vs 原项目10,000行，减少70%)
- 📁 核心文件: 30个Python/Markdown文件
- 🎯 设计目标: 简洁、高效、可维护

**🔥 核心特性: 视觉分析**:
- AnalyzerDecider不仅看文本日志，还能**直接看图像**
- 对比原始输入图像 vs 工具生成的图像
- 精准诊断视觉处理问题（翻转错误、对比度不足、缺失元素等）
- 详见: `VISUAL_ANALYSIS_EXAMPLE.md`

---

## 🚀 快速运行（3步）

### 1. 安装依赖

```bash
cd vision_agent_evolve
pip install -e .
```

### 2. 配置VLM

```bash
# 使用OpenAI (推荐)
export VLM_BASE_URL="https://api.openai.com/v1"
export VLM_API_KEY="sk-your-api-key-here"
export VLM_MODEL="gpt-4o"

# 或使用本地vLLM
export VLM_BASE_URL="http://localhost:8000/v1"
export VLM_API_KEY="EMPTY"
export VLM_MODEL="your-model-name"
```

### 3. 准备测试数据

```bash
# 创建测试图像目录
mkdir -p datasets/mira/images

# 复制一张镜像时钟图像
cp /path/to/your/mirror_clock_image.png datasets/mira/images/mirror_clock_001.png

# 编辑example文件，确保路径正确
cat datasets/mira/example_001.json
```

---

## 📖 运行方式

### 方式1: Evolution模式（核心功能）

**在单个例子上不断尝试，直到解决**

```bash
cd vision_agent_evolve

python run.py \
  --mode evolve \
  --example datasets/mira/example_001.json \
  --max-attempts 10
```

**会发生什么**:
1. ✨ Agent尝试解决任务
2. ❌ 失败 → 分析原因
3. 🛠️ 生成Tool或Skill
4. ✅ 验证并保留有效的
5. 🔄 重复，直到成功或达到max_attempts

**输出位置**:
- `learned/tools/` - 生成的工具代码
- `learned/skills/` - 生成的技能文档
- `learned/evolution_log.jsonl` - 进化历史
- `artifacts/` - 运行时生成的工件

### 方式2: Test模式（快速测试）

**用当前能力运行一次，不进化**

```bash
python run.py \
  --mode test \
  --example datasets/mira/example_001.json
```

用于：
- 测试基础工具是否工作
- 验证新生成的能力
- 调试问题

### 方式3: 直接使用工具

```bash
# 恢复镜像时钟
python -m tools mirror_clock restore input.png output.png

# 回答时钟问题
python -m tools mirror_clock answer image.png "What time is shown?"
```

---

## 📂 项目结构说明

```
vision_agent_evolve/
├── 📄 README.md              ← 完整文档
├── 📄 QUICKSTART.md          ← 快速开始指南
├── 📄 program.md             ← 人工指导（可编辑！）
├── 📄 run.py                 ← 主入口程序
├── 📄 pyproject.toml         ← 依赖配置
│
├── 📁 core/                  ← Agent核心引擎
│   ├── agent.py             # ReAct agent
│   ├── vlm_client.py        # VLM客户端
│   ├── types.py             # 数据类型
│   └── parser.py            # 响应解析
│
├── 📁 skills/                ← Skill系统
│   ├── base.py              # Skill类
│   ├── loader.py            # 加载器
│   ├── renderer.py          # 渲染器
│   └── library/             # Skill库
│       ├── foundation/      # 基础技能
│       │   ├── vision_analysis.md
│       │   └── reasoning.md
│       └── mirror_clock/    # 任务技能
│           └── SKILL.md
│
├── 📁 tools/                 ← Tool系统
│   ├── __main__.py          # CLI入口
│   ├── base.py              # Tool接口
│   ├── registry.py          # 注册表
│   └── implementations/     # 工具实现
│       ├── shared/          # 共享模块
│       │   ├── image_utils.py
│       │   └── vlm_helper.py
│       └── mirror_clock/    # 镜像时钟工具
│           ├── restore.py
│           └── answer.py
│
├── 📁 evolution/             ← 进化系统
│   ├── loop.py              # 主循环
│   ├── roles.py             # 角色（2个）
│   ├── validator.py         # 验证器
│   ├── store.py             # 存储
│   └── types.py             # 数据类型
│
├── 📁 learned/               ← 学到的能力（自动生成）
│   ├── tools/               # 生成的工具
│   ├── skills/              # 生成的技能
│   └── evolution_log.jsonl  # 进化日志
│
└── 📁 datasets/              ← 数据集
    └── mira/
        ├── example_001.json
        └── images/
```

---

## ⚙️ 核心设计特点

### 1. 简化角色系统（10个 → 2个）

**原系统**: Analyzer → Decider → ToolGenerator → SkillGenerator → Reviewer → ...（10个角色，8+ LLM调用）

**新系统**:
- **AnalyzerDecider**: 分析失败 + 决策下一步（1个LLM调用）
- **Generator**: 生成Tool或Skill（1-2个LLM调用）

**结果**: 每次迭代只需2-3个LLM调用

### 2. 简化验证流程（6层 → 3层）

**原系统**: syntax_ok, load_ok, contract_ok, origin_case_ok, regression_ok, skill_ok

**新系统**:
1. **Static**: 语法检查
2. **Origin**: 是否解决原始case？（最重要！）
3. **Regression**: 是否破坏已解决的case？（可选）

### 3. 单例聚焦模式

**原系统**: 批量处理所有case，每个case尝试1次

**新系统**: 聚焦单个case，不断尝试直到解决或放弃

**优势**:
- 确保每个case被深度探索
- 学到的能力更有针对性
- 避免浅尝辄止

### 4. 增强的Skill系统

**原系统**: 只是"使用手册"
```markdown
## Standard Command
python -m glue_swe.tool_cli ...
```

**新系统**: 策略性文档
```markdown
## When to Use
## Strategy (分步骤)
## Common Failures (失败处理)
## Example (完整示例)
```

---

## 🎯 预期效果对比

| 维度 | 原Glue_SWE | Vision Agent Evolve | 改进 |
|------|-----------|---------------------|------|
| **代码量** | 10,000行 | ~3,000行 | -70% |
| **LLM调用/迭代** | 8+ | 2-3 | -70% |
| **角色数量** | 10 | 2 | -80% |
| **验证层级** | 6 | 3 | -50% |
| **最大文件** | 2,185行 | <200行 | -90% |
| **单文件责任** | 混杂 | 单一清晰 | ✨ |
| **聚焦模式** | 批量 | 单例深度 | 🆕 |

---

## 🔧 高级用法

### 监控Evolution过程

```bash
# 实时查看进化日志
tail -f learned/evolution_log.jsonl

# 查看生成了哪些工具
ls -lh learned/tools/

# 查看生成了哪些技能
find learned/skills/ -name "*.md"
```

### 调整Evolution策略

编辑 `program.md`:

```markdown
## Current Focus
- 优先尝试CV-only方案
- 只有CV失败时才用VLM

## Strategy Adjustments
- 如果工具生成失败3次，切换到只生成skill
- 如果镜像恢复总是失败，尝试其他变换
```

### 批量运行多个例子

```bash
#!/bin/bash
for example in datasets/mira/*.json; do
    echo "=== Processing $example ==="
    python run.py --mode evolve --example "$example" --max-attempts 5
    echo ""
done
```

### 分析成功率

```bash
# 查看evolution日志中的成功/失败统计
jq -s '[.[] | select(.solve_success != null)] | group_by(.solve_success) | map({success: .[0].solve_success, count: length})' learned/evolution_log.jsonl
```

---

## 🐛 常见问题排查

### 1. Import错误

```
ModuleNotFoundError: No module named 'core'
```

**解决**:
```bash
# 确保在项目根目录
cd vision_agent_evolve
pwd  # 应该显示 .../vision_agent_evolve

# 重新安装
pip install -e .
```

### 2. VLM连接失败

```
OpenAI connection error
```

**检查**:
```bash
# 验证环境变量
echo $VLM_BASE_URL
echo $VLM_API_KEY

# 测试连接
curl $VLM_BASE_URL/models -H "Authorization: Bearer $VLM_API_KEY"
```

### 3. 图像文件找不到

```
FileNotFoundError: Image not found
```

**解决**:
- 检查 `example_001.json` 中的路径是否正确
- 使用绝对路径或相对于工作目录的路径
- 确保图像文件确实存在

### 4. 生成的代码有语法错误

**原因**: VLM生成的代码可能不完美

**解决**:
1. 使用更强的VLM模型（GPT-4或更好）
2. 检查 `evolution/roles.py` 中的prompts
3. 给evolution更简单的例子开始

### 5. Validation一直失败

**调试**:
```bash
# 查看最近的validation结果
tail -20 learned/evolution_log.jsonl | jq '.validation'

# 手动测试生成的工具
python learned/tools/generated_tool.py test_args
```

---

## 📚 相关文档

在 `vision_agent_evolve/` 目录下:

1. **README.md** - 完整的项目文档和架构说明
2. **QUICKSTART.md** - 5分钟快速开始指南
3. **program.md** - Evolution的人工指导文档（可编辑）
4. **PROJECT_ANALYSIS_AND_REDESIGN.md** - 原项目分析和设计思路（在上级目录）

---

## 💡 使用建议

### 第一次运行

1. **从简单开始**: 用一个清晰的镜像时钟图像
2. **观察过程**: 看控制台输出，了解evolution在做什么
3. **检查结果**: 看 `learned/` 目录下生成了什么
4. **调整策略**: 根据观察编辑 `program.md`

### 持续改进

1. **收集更多例子**: 不同类型的镜像时钟
2. **观察模式**: 哪些总是失败？哪些总是成功？
3. **手动优化**: 编辑生成的tool/skill使其更好
4. **扩展任务**: 不仅是镜像时钟，尝试其他puzzle

### 最佳实践

- ✅ 每次只专注一个问题类型
- ✅ 保存有用的工具和技能（git commit）
- ✅ 定期清理无用的生成物
- ✅ 记录learnings到 `program.md`
- ✅ 从失败中学习，调整策略

---

## 🎓 学习路径

1. **理解架构** (30分钟)
   - 阅读 README.md
   - 查看代码结构
   - 理解各组件职责

2. **运行基本示例** (1小时)
   - 配置环境
   - 准备测试数据
   - 运行test模式
   - 运行evolve模式

3. **观察Evolution** (2小时)
   - 看它如何分析失败
   - 看它生成什么tool/skill
   - 看validation过程

4. **调整和优化** (持续)
   - 编辑program.md
   - 改进prompts
   - 扩展到新问题

---

## 🌟 下一步建议

### 立即可做

1. ✅ 安装依赖
2. ✅ 配置VLM
3. ✅ 准备一个测试图像
4. ✅ 运行test模式验证基础工具
5. ✅ 运行evolve模式看自我进化

### 短期目标（1周内）

- 在5-10个镜像时钟例子上测试
- 观察生成的工具和技能质量
- 调整program.md策略
- 记录成功率和失败模式

### 中期目标（1个月内）

- 扩展到其他视觉puzzle类型
- 优化生成的tool代码
- 改进skill文档质量
- 实现工具复用

### 长期目标（3个月内）

- 建立完整的能力库
- 实现跨任务知识转移
- 达到70%+解决率
- 贡献改进回社区

---

## 🙋 需要帮助？

1. 查看 `README.md` - 完整文档
2. 查看 `QUICKSTART.md` - 快速指南
3. 查看 `PROJECT_ANALYSIS_AND_REDESIGN.md` - 设计思想
4. 查看代码注释 - 详细说明
5. 查看evolution log - 看发生了什么

---

**祝你使用愉快！** 🚀

如果遇到问题或有改进建议，欢迎反馈！
