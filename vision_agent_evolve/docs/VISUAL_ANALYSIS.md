# 视觉分析功能 (Visual Analysis Feature)

## 概述

Vision Agent Evolve 的一个核心优势是**多模态失败分析**：当agent失败时，AnalyzerDecider不仅可以看到文本日志，还能直接看到：

1. 📸 **原始输入图像** - 任务的初始图像
2. 🖼️ **工具生成的图像** - 每个工具调用产生的中间结果图像
3. 📊 **执行轨迹** - Agent的思考和行动序列

这使得失败分析更加准确，因为VLM可以直接观察：
- ✅ 工具是否正确处理了图像
- ✅ 处理结果的质量如何
- ✅ 视觉上是否有问题（模糊、错误变换、缺失元素等）
- ✅ 输出是否符合任务需求

---

## 工作原理

### 1. Artifacts收集

每个工具调用产生的文件（图像、JSON等）会被自动收集：

```python
# 工具返回结果时声明artifacts
ToolResult(
    status="ok",
    answer="restored_clock.png",
    artifacts=["restored_clock.png"],  # ← 这些会被收集
)
```

Agent在执行时自动提取：
```python
# AgentStep记录每步的artifacts
step.artifacts = ["restored_clock.png"]

# AgentResult汇总所有artifacts
result.all_artifacts = ["restored_clock.png", "debug_output.png", ...]
```

### 2. 图像过滤

只有图像文件会被用于视觉分析：

```python
result.get_image_artifacts()  # 自动过滤 .png, .jpg, .jpeg, .gif, .webp
```

### 3. 多模态分析

AnalyzerDecider构建包含图像的消息：

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "分析文本..."},
            {"type": "text", "text": "--- 原始输入图像 ---"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            {"type": "text", "text": "--- 工具生成的图像 ---"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
        ]
    }
]
```

VLM可以：
- 对比原始图像和处理后图像
- 识别处理错误（如翻转方向错误、裁剪位置不对）
- 发现质量问题（模糊、噪声、伪影）
- 理解为什么工具输出不符合预期

---

## 使用示例

### 示例1: 镜像时钟失败分析

**任务**: "This is a mirror clock. What time is shown?"

**执行过程**:
1. Agent调用 `mirror_clock restore input.png`
2. 工具生成 `restored_clock.png`
3. Agent调用 `mirror_clock answer restored_clock.png`
4. 最终答案错误

**传统分析**（仅文本）:
```
Root cause: Tool output was incorrect
Missing capability: Better restoration algorithm
```

**视觉分析**（新功能）:
```
AnalyzerDecider看到:
- 原图: 镜像时钟，时针指向2，分针指向6
- restored_clock.png: 翻转后时针指向10，分针指向6

分析:
Root cause: Restoration tool flipped horizontally but clock hands
            show 10:30 instead of expected 2:30. The flip was correct
            but VLM misread the hour hand position.

Missing capability: Need better hand angle detection or clearer
                   restoration quality check

Next action: generate_tool (create a tool to validate restoration
            by checking if hour/minute hand angles are reasonable)
```

**优势**: 直接看到问题所在，给出更精准的解决方案。

### 示例2: 图像处理质量问题

**任务**: "Defuse the bomb by finding matching pairs"

**执行过程**:
1. Agent调用 `defuse_bomb extract_wires input.png`
2. 生成 `wires_extracted.png` (但提取不完整)
3. Agent基于不完整的提取结果给出答案
4. 失败

**视觉分析**:
```
AnalyzerDecider看到:
- 原图: 5根彩色线
- wires_extracted.png: 只提取出3根线，2根被背景噪声干扰遗漏

分析:
Root cause: Wire extraction tool missed 2 wires due to low contrast
            with background. Visual inspection shows extraction is
            incomplete.

Missing capability: More robust edge detection or pre-processing
                   to enhance contrast before extraction

Next action: generate_tool (create preprocessing tool to enhance
            contrast before wire extraction)
```

---

## 控制台输出示例

运行evolution时，你会看到：

```
--- Attempt 3/10 ---
Solving with current capabilities...
✗ Failed. Answer: 10:30 (expected: 02:30)
  Artifacts generated: 2
    - artifacts/restored_clock.png
    - artifacts/debug_angles.png

Analyzing failure with visual context...
  → Original image: datasets/mira/images/mirror_clock_001.png
  → Processing 2 artifact images for analysis

Analysis: Horizontal flip correct but hour hand angle misread
Next action: generate_tool
```

---

## 技术实现细节

### Artifacts流转

```
Tool.run()
  ↓ returns ToolResult(artifacts=["file.png"])
  ↓
Agent._extract_artifacts(observation)
  ↓ parses "ARTIFACTS: file.png"
  ↓ adds to step.artifacts
  ↓
AgentResult.all_artifacts
  ↓ collects from all steps
  ↓
AnalyzerDecider.analyze_and_decide()
  ↓ filters images via get_image_artifacts()
  ↓ encodes to base64
  ↓ sends to VLM in multimodal message
```

### 图像编码

```python
import base64
from pathlib import Path

# 读取图像
with open(image_path, "rb") as f:
    img_data = base64.b64encode(f.read()).decode()

# 确定MIME类型
suffix = Path(image_path).suffix.lower()
mime_map = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
}
mime = mime_map.get(suffix, 'image/png')

# 构建data URL
data_url = f"data:{mime};base64,{img_data}"
```

### 限制

- **最多3张artifact图像**: 避免超过VLM的上下文限制
- **图像大小**: 依赖VLM的限制（通常<20MB）
- **格式支持**: png, jpg, jpeg, gif, webp

---

## 配置选项

### 在program.md中调整

```markdown
## Visual Analysis Strategy

When analyzing failures:
- Always compare original vs processed images
- Look for transformation errors (wrong flip, rotation)
- Check for quality degradation (blur, artifacts)
- Verify completeness (missing elements)

If visual analysis shows:
- Correct transformation → generate_skill (improve reasoning)
- Wrong transformation → generate_tool (fix processing)
- Quality issues → generate_tool (add preprocessing)
```

### 调试模式

查看发送给VLM的完整内容：

```python
# 在 evolution/roles.py 的 analyze_and_decide 中添加
print("=== Sending to VLM ===")
print(f"Text parts: {len([p for p in content_parts if p['type'] == 'text'])}")
print(f"Image parts: {len([p for p in content_parts if p['type'] == 'image_url'])}")
print("======================")
```

---

## 最佳实践

### 1. 工具设计

确保工具返回有意义的artifacts：

```python
class MyTool(Tool):
    def run(self, image_path: str) -> ToolResult:
        # 处理图像
        processed = process_image(image_path)

        # 保存中间结果（便于分析）
        output_path = "processed_output.png"
        save_image(processed, output_path)

        return ToolResult(
            status="ok",
            answer="processed",
            artifacts=[output_path],  # ← 关键！
        )
```

### 2. Skill指导

在skill中提示agent保存调试图像：

```markdown
## Debugging

If the tool has a --debug flag, use it:

```bash
python -m tools my_tool process image.png --debug
```

This will save intermediate results for later analysis.
```

### 3. 命名规范

使用描述性的artifact文件名：

```python
# Good
artifacts=[
    "step1_restored.png",
    "step2_enhanced.png",
    "step3_segmented.png"
]

# Bad
artifacts=[
    "output.png",
    "temp.png",
    "result.png"
]
```

---

## 局限与未来改进

### 当前局限

1. **数量限制**: 只分析前3张artifact图像
2. **大小限制**: 依赖VLM的图像大小限制
3. **格式限制**: 只支持常见图像格式
4. **无视频**: 暂不支持视频artifacts

### 计划改进

- [ ] 支持选择最重要的artifacts（而非仅前3张）
- [ ] 添加图像压缩/缩放以适应VLM限制
- [ ] 支持视频帧采样分析
- [ ] 支持并排对比视图（原图vs处理图）
- [ ] 添加图像diff高亮显示差异

---

## FAQ

**Q: 如果工具没有生成图像怎么办？**

A: 分析会退化为纯文本模式，仍然可以工作，只是准确性可能降低。

**Q: 会不会增加很多LLM成本？**

A: 会有一定增加（图像输入成本较高），但换来的是更准确的分析，减少无效的tool生成尝试，整体可能更省。

**Q: 原始图像很大会不会有问题？**

A: VLM通常会自动缩放，但如果超过限制会报错。建议在datasets中使用合理大小的图像（<5MB）。

**Q: 可以只分析原图，不分析artifacts吗？**

A: 可以，但artifacts是关键——它们显示了工具实际做了什么，vs应该做什么。强烈建议保留。

**Q: 如何验证视觉分析是否生效？**

A: 查看控制台输出：
```
Analyzing failure with visual context...
  → Original image: xxx.png
  → Processing 2 artifact images for analysis
```
如果看到这些行，说明视觉分析已启用。

---

## 示例输出对比

### 无视觉分析（旧版本）

```
Analysis: Tool failed
Root cause: Unknown
Missing capability: Better tool
Next action: generate_tool
```

### 有视觉分析（新版本）

```
Analysis: Restoration flipped image but hour hand angle detection failed
Root cause: VLM misread hour hand as 10 instead of 2 due to ambiguous
           position in restored image. Original image shows clear 2:30
           but restoration introduced slight blur making hour hand
           position less distinct.
Missing capability: Post-restoration validation to verify hand angles
                   match expected ranges (hour hand should be near 2
                   for 2:30, not near 10)
Next action: generate_tool (validation tool to check restored clock
            hand angles against reasonable bounds)
Confidence: 0.85
```

**差异明显！** 新版本给出了可执行的、具体的改进方向。

---

这个功能是Vision Agent Evolve的核心竞争力之一。充分利用VLM的视觉能力，让evolution更智能、更精准！ 🎯
