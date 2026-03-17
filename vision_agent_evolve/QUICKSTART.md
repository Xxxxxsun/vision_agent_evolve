# Vision Agent Evolve - 快速开始指南

## 🚀 5分钟快速开始

### 步骤1: 安装依赖

```bash
cd vision_agent_evolve

# 创建项目内虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖（会使用 numpy<2，避免当前 opencv ABI 冲突）
pip install -e .
```

### 步骤2: 配置VLM连接

设置环境变量：

```bash
# 如果使用OpenAI
export VLM_BASE_URL="https://api.openai.com/v1"
export VLM_API_KEY="your-openai-api-key"
export VLM_MODEL="gpt-4o"

# 或者使用本地vLLM服务
export VLM_BASE_URL="http://localhost:8000/v1"
export VLM_API_KEY="EMPTY"
export VLM_MODEL="your-local-model"
```

### 步骤3: 准备测试图像

创建一个测试镜像时钟图像（或使用你自己的）：

```bash
# 确保图像目录存在
mkdir -p datasets/mira/images

# 把你的测试图像复制到这里
cp /path/to/your/mirror_clock.png datasets/mira/images/mirror_clock_001.png
```

### 步骤4: 测试工具

```bash
# 测试镜像恢复工具
python -m tools mirror_clock restore datasets/mira/images/mirror_clock_001.png

# 测试回答工具
python -m tools mirror_clock answer restored_clock.png "What time is shown?"
```

### 步骤5: 运行Evolution Loop

```bash
# 在单个例子上运行进化循环
.venv/bin/python run.py \
  --mode evolve \
  --example datasets/mira/example_001.json \
  --max-attempts 10
```

---

## 📊 运行模式说明

### Evolution模式（进化模式）

**用途**: 让agent在一个例子上不断尝试，自动生成tool和skill直到成功

```bash
.venv/bin/python run.py --mode evolve --example datasets/mira/example_001.json
```

**发生什么**:
1. 尝试用现有能力解决
2. 失败 → 分析原因 → 生成tool/skill
3. 验证新能力
4. 保留有效的，丢弃无效的
5. 重复直到成功或达到max_attempts

**输出**:
- 控制台: 每次尝试的详细过程
- `learned/tools/`: 生成的工具代码
- `learned/skills/`: 生成的技能文档
- `learned/evolution_log.jsonl`: 完整进化日志

### Test模式（测试模式）

**用途**: 用当前能力运行一次，不进化

```bash
.venv/bin/python run.py --mode test --example datasets/mira/example_001.json
```

**用于**:
- 测试当前能力
- 验证新生成的tool/skill
- 调试问题

---

## 📝 创建自己的示例

创建 `datasets/mira/my_example.json`:

```json
{
  "id": "my_test_001",
  "problem_id": "mirror_clock",
  "prompt": "This is what a clock looks like in a mirror. What time is shown?",
  "answer": "14:30",
  "image": "datasets/mira/images/my_test_001.png"
}
```

然后运行：
```bash
.venv/bin/python run.py --mode evolve --example datasets/mira/my_example.json
```

---

## 🔍 监控和调试

### 查看学到的能力

```bash
# 查看生成的工具
ls -lh learned/tools/

# 查看生成的技能
ls -lh learned/skills/

# 查看进化日志
tail -f learned/evolution_log.jsonl | jq
```

### 手动测试生成的工具

如果evolution生成了 `learned/tools/my_new_tool.py`:

```bash
# 查看代码
cat learned/tools/my_new_tool.py

# 如果它遵循标准格式，可以这样测试
python learned/tools/my_new_tool.py arg1 arg2
```

### 调整策略

编辑 `program.md` 来引导evolution的方向：

```markdown
## Current Focus
- Try simpler CV approaches first
- Only use VLM if CV fails

## Strategy Adjustments
- If tool generation fails 3 times, switch to skill-only
```

---

## 🐛 常见问题

### Q: "Module not found" 错误

**A**: 确保你在项目根目录：
```bash
cd vision_agent_evolve
python run.py ...
```

### Q: VLM连接失败

**A**: 检查环境变量：
```bash
echo $VLM_BASE_URL
echo $VLM_API_KEY
echo $VLM_MODEL

# 测试连接
curl $VLM_BASE_URL/models -H "Authorization: Bearer $VLM_API_KEY"
```

### Q: 生成的代码有语法错误

**A**:
1. 查看 `evolution/roles.py` 中的Generator prompts
2. 给它更简单的例子先
3. 检查VLM模型是否足够强大（推荐GPT-4或以上）

### Q: Evolution一直失败

**A**:
1. 降低 `--max-attempts` 到5，更快失败
2. 检查example_001.json中的答案格式是否正确
3. 先用test模式验证基本工具是否工作：
   ```bash
   python run.py --mode test --example datasets/mira/example_001.json
   ```

### Q: 工具找不到图像文件

**A**: 使用绝对路径或相对于工作目录的路径：
```bash
# 在example JSON中
"image": "datasets/mira/images/xxx.png"  # 相对路径
# 或
"image": "/absolute/path/to/image.png"  # 绝对路径
```

---

## 🎯 下一步

1. **尝试更多例子**: 创建多个example JSON，让agent学习不同情况
2. **查看生成的能力**: 看看agent生成了什么工具和技能
3. **调整program.md**: 根据观察调整策略
4. **扩展到其他puzzle**: 不仅是mirror_clock，尝试其他视觉puzzle
5. **贡献改进**: 发现问题？改进prompt或架构

---

## 📚 进阶用法

### 批量运行多个例子

创建脚本 `run_batch.sh`:

```bash
#!/bin/bash
for example in datasets/mira/*.json; do
    echo "Processing $example"
    python run.py --mode evolve --example "$example" --max-attempts 5
done
```

### 分析成功率

```bash
# 统计成功/失败
jq -s 'map(select(.solve_success != null)) | group_by(.solve_success) | map({success: .[0].solve_success, count: length})' learned/evolution_log.jsonl
```

### 复用学到的能力到其他项目

```bash
# 复制学到的工具
cp learned/tools/*.py ../other_project/tools/

# 复制学到的技能
cp -r learned/skills/* ../other_project/skills/
```

---

## 💡 提示

- **从简单开始**: 先用明显的镜像时钟测试，确保基本流程工作
- **观察日志**: evolution的console输出很详细，看它在想什么
- **耐心等待**: 每次迭代包含2-3个LLM调用，需要一些时间
- **调整program.md**: 这是你控制evolution的主要方式
- **保存好的结果**: git commit学到的有用工具和技能

---

## 🆘 需要帮助？

1. 查看 `README.md` 了解架构
2. 查看 `PROJECT_ANALYSIS_AND_REDESIGN.md` 了解设计思想
3. 查看代码注释
4. 检查 `evolution_log.jsonl` 看发生了什么

祝你使用愉快！ 🚀
