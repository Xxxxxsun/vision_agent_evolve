# 修复后的演化流程 - 完整示例

## 🎯 你期望的演化路径（现已实现）

---

## 例子1: 简单镜像时钟

### 输入
```json
{
  "id": "mirror_001",
  "prompt": "What time is shown on this mirror clock?",
  "answer": "02:30",
  "image": "mirrored_clock.png"  // 显示2:30但镜像了
}
```

### 第1次尝试（Iteration 1）

**Agent行为**：
```
1. 读取任务 + 图像
2. Foundation skill "try_direct_first" 激活
3. VLM直接看镜像图像，尝试读取时间
4. VLM回答: "10:30" ❌ (镜像导致混淆)
```

**失败分析**：
```
AnalyzerDecider看到:
📸 原图: 镜像时钟（时针在2，分针在6，但镜像）
🤔 VLM回答: 10:30
✅ 分析: VLM无法正确理解镜像图像，时针位置被误读

FailureAnalysis:
{
  "root_cause": "VLM cannot correctly interpret mirrored clock.
                Hour hand appears at 10 instead of 2 due to mirror reflection.",
  "missing_capabilities": ["mirror_restoration"],
  "next_action": "generate_tool"
}
```

**工具生成**：
```python
# learned/tools/mirror_restore.py
class MirrorRestoreTool(Tool):
    def run(self, image_path: str) -> ToolResult:
        img = load_image(image_path)
        restored = cv2.flip(img, 1)  # 水平翻转
        output = save_image(restored, "artifacts/restored.png")

        return ToolResult(
            status="ok",
            answer=output,
            artifacts=[output]
        )

def main():
    tool = MirrorRestoreTool()
    result = tool.run(sys.argv[1])
    print(result)
```

**验证**：
```
1. Agent调用: python learned/tools/mirror_restore.py mirrored_clock.png
2. 生成: artifacts/restored.png（已翻转，显示正常2:30）
3. Agent再次看图，VLM读取: "02:30" ✓
4. Validation通过！
```

**保存**：
- ✅ Tool: `learned/tools/mirror_restore.py`
- ✅ Skill: `learned/skills/mirror_clock_basic/SKILL.md`

```markdown
## When to Use
- Clock image appears mirrored/reversed
- VLM struggles to read mirrored content

## Strategy
1. Try VLM directly first
2. If mirror detected (digits reversed): Use mirror_restore
3. Read restored image
```

---

## 例子2: 镜像 + 旋转45度

### 输入
```json
{
  "id": "mirror_002",
  "prompt": "What time is shown?",
  "answer": "03:15",
  "image": "mirrored_rotated_clock.png"  // 镜像 + 顺时针旋转45度
}
```

### 第1次尝试（Iteration 1）

**Agent行为**：
```
1. 加载learned skill: mirror_clock_basic
2. 识别到镜像特征
3. 调用: python learned/tools/mirror_restore.py mirrored_rotated_clock.png
4. VLM看恢复后的图像
5. VLM回答: "05:45" ❌ (还有旋转问题)
```

**失败分析**：
```
AnalyzerDecider看到:
📸 原图: 镜像+旋转的时钟
🖼️ Artifact: restored.png（镜像已修复，但还是倾斜45度）
🤔 VLM回答: 05:45（因为旋转，时针位置误判）

FailureAnalysis:
{
  "root_cause": "Mirror restoration succeeded, but clock is rotated 45°.
                Hour hand position relative to 12 o'clock is shifted.",
  "missing_capabilities": ["rotation_correction"],
  "next_action": "generate_tool"
}
```

**工具生成**：
```python
# learned/tools/rotate_correct.py
class RotateCorrectTool(Tool):
    def run(self, image_path: str, angle: float = 0) -> ToolResult:
        img = load_image(image_path)

        # Auto-detect rotation if angle=0
        if angle == 0:
            angle = detect_rotation_angle(img)  # 简单的边缘检测

        # 旋转回正
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
        corrected = cv2.warpAffine(img, matrix, (w, h))

        output = save_image(corrected, "artifacts/rotated.png")

        return ToolResult(
            status="ok",
            answer=output,
            artifacts=[output],
            debug_info=f"Corrected rotation by {-angle}°"
        )
```

**Skill更新**（Merging!）：
```markdown
# learned/skills/mirror_clock_basic/SKILL.md (Updated)

## Previous Knowledge
- Use mirror_restore for mirrored clocks

---

## New Additions

### When Image Has Multiple Issues
- Mirrored + Rotated → Apply tools in sequence

## Tool Chain
```bash
# Step 1: Restore mirror
python learned/tools/mirror_restore.py input.png

# Step 2: Correct rotation
python learned/tools/rotate_correct.py artifacts/restored.png

# Step 3: Read corrected image
(VLM can now read accurately)
```

## Strategy Update
1. Try VLM directly
2. If mirrored: mirror_restore
3. If still wrong AND rotated: rotate_correct
4. Re-read final image
```

**验证**：
```
1. Agent执行工具链:
   - mirror_restore → artifacts/restored.png
   - rotate_correct artifacts/restored.png → artifacts/rotated.png
2. VLM读取artifacts/rotated.png
3. VLM回答: "03:15" ✓
4. Validation通过！
```

**保存**：
- ✅ 新Tool: `learned/tools/rotate_correct.py`
- ✅ 更新Skill: `mirror_clock_basic/SKILL.md` (合并了新知识)

---

## 例子3: 仅旋转（复用工具）

### 输入
```json
{
  "id": "rotate_only_003",
  "prompt": "What time?",
  "answer": "11:00",
  "image": "rotated_30deg.png"  // 只旋转，不镜像
}
```

### 第1次尝试（Iteration 1）

**Agent行为**：
```
1. 加载learned skill (已包含旋转知识)
2. 尝试VLM直接读取
3. VLM: "12:30" ❌ (旋转影响)
4. 识别到旋转问题
5. 直接调用: python learned/tools/rotate_correct.py rotated_30deg.png
6. VLM读取: "11:00" ✓
```

**✨ 无需生成新工具！复用成功！**

---

## 例子4: 复杂组合（镜像 + 旋转 + 模糊）

### 输入
```json
{
  "id": "complex_004",
  "prompt": "What time?",
  "answer": "07:20",
  "image": "blurry_mirrored_rotated.png"
}
```

### 第1次尝试（工具链不够）

**Agent行为**：
```
1. mirror_restore → 部分改善
2. rotate_correct → 进一步改善
3. VLM读取artifacts/rotated.png: "07:00" ❌ (分针因模糊看不清)
```

**失败分析**：
```
AnalyzerDecider看到:
📸 原图: 模糊+镜像+旋转
🖼️ Artifact1: restored.png
🖼️ Artifact2: rotated.png (还是模糊)
🤔 VLM: 07:00（时针对，分针因模糊误判）

FailureAnalysis:
{
  "root_cause": "Mirror and rotation corrected, but image is blurry.
                Minute hand position unclear due to blur.",
  "missing_capabilities": ["deblur", "sharpen"],
  "next_action": "generate_tool"
}
```

**工具生成**：
```python
# learned/tools/enhance_clarity.py
class EnhanceClarityTool(Tool):
    def run(self, image_path: str) -> ToolResult:
        img = load_image(image_path)

        # 锐化
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(img, -1, kernel)

        # 降噪
        denoised = cv2.fastNlMeansDenoisingColored(sharpened)

        output = save_image(denoised, "artifacts/enhanced.png")
        return ToolResult(status="ok", answer=output, artifacts=[output])
```

**Skill再次更新**：
```markdown
## Tool Chain (Extended)
For complex cases:
```bash
# 1. Mirror correction (if mirrored)
python learned/tools/mirror_restore.py input.png

# 2. Rotation correction (if rotated)
python learned/tools/rotate_correct.py artifacts/restored.png

# 3. Clarity enhancement (if blurry)
python learned/tools/enhance_clarity.py artifacts/rotated.png

# 4. Final reading
(VLM reads artifacts/enhanced.png)
```

Apply in order, skip steps that aren't needed.
```

**第2次尝试（完整工具链）**：
```
1. mirror_restore
2. rotate_correct
3. enhance_clarity
4. VLM读取: "07:20" ✓
```

---

## 🎯 演化总结

### 工具库的成长

```
Iteration 0: 无工具
  ↓
Iteration 1: mirror_restore
  ↓
Iteration 2: mirror_restore + rotate_correct
  ↓
Iteration 3: (复用已有工具)
  ↓
Iteration 4: mirror_restore + rotate_correct + enhance_clarity
```

### Skill的进化

```
Version 1:
- Try direct → use mirror_restore if mirrored

Version 2 (Merged):
- Try direct
- If mirrored: mirror_restore
- If rotated: rotate_correct
- Tool chain: restore → rotate → read

Version 3 (Further Merged):
- Try direct
- Apply tool chain based on issues detected:
  - Mirrored? → mirror_restore
  - Rotated? → rotate_correct
  - Blurry? → enhance_clarity
- Order matters: restore → rotate → enhance → read
```

### 关键特性（已实现）

✅ **动态工具加载**: learned/tools/里的工具自动可用
✅ **Skill合并**: 新知识被追加到现有skill
✅ **工具复用**: 后续例子自动使用已有工具
✅ **工具链**: Skill明确指导工具使用顺序
✅ **渐进式优化**: 每次只解决一个问题，不断累积

---

## 🔧 技术实现

### 1. 动态工具加载
```python
# tools/__main__.py
learned_tools = discover_learned_tools(learned_dir)
if tool_name in learned_tools:
    execute_learned_tool(learned_tools[tool_name], args)
```

### 2. Skill合并
```python
# evolution/store.py
def promote_skill(self, proposal):
    if skill_file.exists():
        merged = self._merge_skill_content(existing, proposal)
    else:
        merged = new_content
    skill_file.write_text(merged)
```

### 3. Foundation引导
```markdown
# skills/library/foundation/try_direct_first.md
## Strategy
1. Try VLM directly
2. If fail: Analyze why
3. Generate tool (if needed)
4. Update skill
5. Next time: Use tool strategically
```

### 4. 工具链支持
```markdown
# Generated skill includes:
## Tool Chain
tool_a → tool_b → tool_c → vlm_read
```

---

## ✅ 现在能达到你的期望了！

**你的演化路径**：
```
例子1 (镜像) → 生成mirror_restore → 保存
例子2 (镜像+旋转) → 复用mirror_restore + 生成rotate_correct → 更新skill
例子3 (旋转) → 复用rotate_correct → 成功
例子4 (复杂) → 复用所有 + 生成enhance_clarity → 再次更新skill
```

**系统行为**：
- ✅ VLM先直接尝试
- ✅ 失败后分析根因（有视觉证据）
- ✅ 生成针对性工具
- ✅ 验证工具有效性
- ✅ 保存并合并到skill
- ✅ 后续例子自动复用
- ✅ 不断优化工具链

**这就是真正的自我进化！** 🚀
