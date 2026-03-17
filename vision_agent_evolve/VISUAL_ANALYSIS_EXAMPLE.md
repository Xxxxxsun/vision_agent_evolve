# 视觉分析功能示例

## 🎯 核心改进：AnalyzerDecider能看到图像！

### 问题：为什么需要视觉分析？

**场景**: Agent在镜像时钟任务上失败了

**传统方式（仅文本日志）**:
```
Tool output: "ANSWER: 10:30"
Expected: "02:30"
Error: Answer mismatch
```

**AnalyzerDecider的盲点**:
- ❌ 看不到原始图像什么样
- ❌ 看不到工具处理后的图像
- ❌ 不知道是工具处理错了，还是理解错了
- ❌ 只能猜测问题所在

**结果**: 生成的tool/skill可能偏离真正的问题。

---

### 解决方案：多模态失败分析

**现在AnalyzerDecider能看到**:

```
📸 原始图像: mirror_clock_001.png
   ├─ 镜像时钟
   ├─ 时针指向2
   └─ 分针指向6

🖼️ 工具输出1: restored_clock.png
   ├─ 水平翻转后的时钟
   ├─ 时针看起来指向10（实际应该是2）
   └─ 分针指向6（正确）

🖼️ 工具输出2: debug_angles.png
   └─ 显示检测到的角度标注
```

**AnalyzerDecider的分析**:
```json
{
  "root_cause": "Restoration tool correctly flipped the image horizontally,
                but the hour hand position at approximately 60° was misinterpreted
                as 10 o'clock (300°) instead of 2 o'clock (60°) in the restored image.
                Visual comparison shows the flip was correct but angle detection
                needs calibration.",

  "failure_stage": "execution - tool output interpretation",

  "missing_capabilities": [
    "Hour hand angle validation (should be 30° per hour from 12)",
    "Post-restoration sanity check for clock hand positions"
  ],

  "next_action": "generate_tool",

  "rationale": "Visual evidence clearly shows the restoration was geometrically
               correct (proper horizontal flip) but the subsequent angle reading
               by VLM was off by 8 hours. Need a validation tool that checks if
               detected angles fall within reasonable bounds for the expected time."
}
```

**优势**:
- ✅ **精准诊断**: 明确问题是角度解读，不是翻转算法
- ✅ **可执行方案**: 生成角度验证工具，而非重写翻转逻辑
- ✅ **避免浪费**: 不会生成不必要的工具

---

## 实际运行示例

### 运行命令

```bash
python run.py --mode evolve --example datasets/mira/example_001.json --max-attempts 5
```

### 控制台输出

```
============================================================
Evolution Loop: mirror_clock_001
Task: This is what a clock looks like in a mirror. What time will it be in 1 hours and 40 minutes?
============================================================

--- Attempt 1/5 ---
Solving with current capabilities...
✗ Failed. Answer: 11:50 (expected: 04:10)
  Artifacts generated: 1
    - artifacts/restored_clock.png

Analyzing failure with visual context...
  → Original image: datasets/mira/images/mirror_clock_001.png
  → Processing 1 artifact images for analysis

Analysis: Clock was restored but time calculation was completely wrong.
          Visual inspection shows restored image has hour hand near 2 and
          minute hand at 6 (2:30), but agent calculated 11:50. The VLM
          failed to correctly read the restored clock time before adding
          1h40m.

Next action: generate_tool

Generating tool...
Generated: clock_time_reader

Validating tool...
✓ Validation passed! Promoting tool...

--- Attempt 2/5 ---
Solving with current capabilities...
✓ SOLVED! Answer: 04:10

✓✓✓ SUCCESS! Case solved. ✓✓✓
```

### 生成的工具

AnalyzerDecider看到了restored_clock.png后，知道翻转是对的，问题在于时间读取。生成了：

**learned/tools/clock_time_reader.py** (简化版):
```python
class ClockTimeReaderTool(Tool):
    """Read time from clock image by detecting hand angles."""

    def run(self, image_path: str) -> ToolResult:
        img = load_image(image_path)

        # Detect hour and minute hands
        hour_angle = detect_hour_hand(img)
        minute_angle = detect_minute_hand(img)

        # Convert angles to time
        hours = int((hour_angle % 360) / 30)
        minutes = int((minute_angle % 360) / 6)

        # Validation: hour hand should align with minute hand
        expected_hour_angle = (hours * 30 + minutes / 2) % 360
        if abs(hour_angle - expected_hour_angle) > 15:
            return ToolResult(
                status="error",
                answer="",
                error=f"Hour hand angle {hour_angle}° inconsistent with time {hours}:{minutes:02d}"
            )

        return ToolResult(
            status="ok",
            answer=f"{hours:02d}:{minutes:02d}",
        )
```

**为什么这个工具有用**:
- 因为AnalyzerDecider**看到**了restored_clock.png
- 知道翻转是正确的
- 问题在于如何从图像读取时间
- 所以生成了专门的时间读取工具

---

## 对比：无视觉分析 vs 有视觉分析

### 场景：炸弹拆除任务

**任务**: "Match the colored wires to defuse the bomb"

**Agent执行**:
1. 调用 `extract_wires input.png`
2. 生成 `wires_extracted.png`（但只提取了3/5根线）
3. 基于不完整结果给出答案
4. 失败

---

### 方式A: 无视觉分析（纯文本）

**看到的信息**:
```
Tool: extract_wires
Output: Found 3 wires: red, blue, green
Expected answer: red-blue, green-yellow, black-white
Agent's answer: red-blue
Result: Wrong
```

**分析（猜测）**:
```json
{
  "root_cause": "Tool only found 3 wires but there should be 5",
  "next_action": "generate_tool",
  "rationale": "Need better wire detection algorithm"
}
```

**生成的工具**: 可能重写整个提取算法，但不知道具体哪里错了。

---

### 方式B: 有视觉分析（多模态）

**看到的信息**:
```
📸 原始图像: bomb_puzzle.png
   - 5根线清晰可见: 红、蓝、绿、黄、黑
   - 背景：灰色金属面板
   - 黄色和黑色线的对比度较低（与背景接近）

🖼️ wires_extracted.png:
   - 只显示3根线: 红、蓝、绿
   - 黄色和黑色线完全缺失
   - 提取区域正确，但颜色阈值可能太严格
```

**分析（基于视觉证据）**:
```json
{
  "root_cause": "Wire extraction missed yellow and black wires due to
                low contrast with gray background. Visual comparison
                shows they are present in original but absent in extracted
                image. The RGB color thresholding likely filtered them out.",

  "failure_stage": "execution - preprocessing/feature extraction",

  "missing_capabilities": [
    "Contrast-adaptive color detection",
    "Pre-processing to enhance low-contrast elements"
  ],

  "next_action": "generate_tool",

  "rationale": "Need a preprocessing step to enhance contrast before color
               extraction, or use HSV color space which is more robust to
               brightness variations. Visual evidence shows the wires exist
               but current RGB thresholding can't detect them."
}
```

**生成的工具**:
```python
class ContrastEnhancedWireExtractor(Tool):
    """Extract wires with contrast enhancement preprocessing."""

    def run(self, image_path: str) -> ToolResult:
        img = load_image(image_path)

        # Convert to LAB color space
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)

        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        lab[:,:,0] = clahe.apply(lab[:,:,0])

        # Convert back
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        # Now extract wires (will catch low-contrast ones)
        wires = extract_colored_regions(enhanced)

        return ToolResult(
            status="ok",
            answer=str(wires),
            artifacts=["wires_enhanced.png", "wires_extracted.png"]
        )
```

**为什么更好**:
- ✅ 直接看到问题：低对比度
- ✅ 针对性解决：CLAHE增强对比度
- ✅ 不是盲目重写：知道RGB阈值本身没问题，只是缺前处理

---

## 技术实现概览

### 1. Artifacts自动收集

```python
# 工具返回时声明artifacts
def run(self, image_path: str) -> ToolResult:
    processed = process_image(image_path)
    output_path = save_image(processed, "output.png")

    return ToolResult(
        status="ok",
        answer="processed",
        artifacts=[output_path]  # ← 自动被收集
    )
```

### 2. Agent提取和汇总

```python
# AgentStep记录每步artifacts
for turn in range(max_turns):
    observation = run_tool(...)
    step.artifacts = extract_artifacts_from_observation(observation)
    steps.append(step)

# AgentResult汇总
result.all_artifacts = [art for step in steps for art in step.artifacts]
```

### 3. AnalyzerDecider多模态请求

```python
# 构建包含图像的消息
content = [
    {"type": "text", "text": "分析这个失败..."},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},  # 原图
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},  # artifact 1
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},  # artifact 2
]

response = vlm_client.chat([{"role": "user", "content": content}])
```

### 4. VLM分析

VLM (如GPT-4o, Claude 3.5 Sonnet)可以：
- 对比原图和处理图的差异
- 识别处理错误（翻转方向、裁剪位置、颜色失真等）
- 发现质量问题（模糊、噪声、缺失元素）
- 推断根本原因

---

## 最佳实践

### 工具开发

**DO**: 返回有意义的中间结果
```python
def run(self, image: str) -> ToolResult:
    step1 = preprocess(image)
    save_image(step1, "step1_preprocessed.png")

    step2 = extract_features(step1)
    save_image(step2, "step2_features.png")

    final = postprocess(step2)
    save_image(final, "final_result.png")

    return ToolResult(
        status="ok",
        answer="result",
        artifacts=[
            "step1_preprocessed.png",
            "step2_features.png",
            "final_result.png"
        ]
    )
```

**DON'T**: 只返回最终结果
```python
def run(self, image: str) -> ToolResult:
    result = process(image)  # 黑盒处理
    return ToolResult(status="ok", answer="done")  # AnalyzerDecider看不到中间过程
```

### Skill指导

在skill中建议保存调试图像：
```markdown
## Debugging

When a tool fails, use its --debug flag to save intermediate images:

```bash
python -m tools my_tool process image.png --debug
```

This helps evolution understand what went wrong visually.
```

---

## 限制与注意事项

1. **数量限制**: 当前只分析前3张图像artifacts（避免超VLM限制）
2. **大小限制**: 图像应<20MB（VLM限制）
3. **成本**: 图像输入比文本贵，但换来更准确的分析
4. **格式**: 支持 .png, .jpg, .jpeg, .gif, .webp

---

## 总结

| 方面 | 无视觉分析 | 有视觉分析 |
|------|-----------|----------|
| 看到的信息 | 文本日志 | 原图 + 处理图 + 日志 |
| 分析准确性 | 猜测为主 | 基于视觉证据 |
| 生成的工具 | 可能偏离问题 | 针对性强 |
| 迭代次数 | 更多尝试 | 更快收敛 |
| 总体成本 | 单次便宜，总次数多 | 单次贵，但总次数少 |

**结论**: 视觉分析是值得的！它大幅提升了evolution的智能程度。 🎯
