---
name: try_direct_first
description: "Foundation strategy: try VLM directly before using tools"
level: foundation
depends_on: []
---

# Try Direct First

## Core Principle

**Always attempt to solve with VLM's native capabilities before reaching for tools.**

## Why This Matters

Tools have costs:
- Development time
- Maintenance burden
- Potential bugs
- Slower execution

VLM might already be able to handle the task if you:
- Provide clear instructions
- Include the image
- Ask the right questions

## Strategy

### Phase 1: Direct Attempt

```
1. Observe the image carefully
2. Understand what the task asks
3. Attempt to answer directly using VLM reasoning
4. If you can answer confidently → TASK_COMPLETE
```

### Phase 2: Recognize Limitations

If direct attempt fails, analyze **why**:
- ❓ **Can't see clearly** → Need image preprocessing (enhance, restore)
- ❓ **Can't understand structure** → Need feature extraction
- ❓ **Can't compute** → Need calculation tool
- ❓ **Ambiguous/Confusing** → Need clarification or transformation

### Phase 3: Tool-Assisted Approach

Only use tools when you've identified **specific limitations**:

```markdown
Example:
- Task: "What time is shown on this mirror clock?"
- Direct attempt: See mirrored clock, try to read
- Problem: Mirrored digits/hands are confusing
- Solution: Use mirror_restore tool
- Retry: After restoration, can read clearly
```

## Anti-Patterns

❌ **Don't**: Immediately reach for tools without trying
```
User: "What time is shown?"
Bad: "Let me use the clock reading tool..."
Good: "Looking at the image, I can see... [attempt first]"
```

❌ **Don't**: Use tools as a crutch for lazy reasoning
```
Bad: "I'll use the answer tool to answer"
Good: "I observe X, Y, Z, therefore the answer is..."
```

## When Tools ARE Necessary

✅ **Geometric transformations**: Mirror, rotate, scale
✅ **Precision calculations**: Angles, distances, pixel values
✅ **Complex feature extraction**: Segmentation, detection
✅ **Format conversions**: OCR, data extraction

## Evolution Trigger

If you repeatedly fail on similar tasks:
1. **Pattern Recognition**: Same type of task, same failure mode
2. **Tool Generation**: Create a tool for this specific transform/computation
3. **Skill Update**: Document when to use the new tool
4. **Next Time**: Try direct first, fall back to tool if needed

## Example Progression

### Iteration 1 (No tools)
```
Task: Mirror clock, what time?
Attempt: Try to read mirrored → Fail (confusing)
```

### Iteration 2 (Tool generated)
```
Task: Same type
Strategy:
  1. Try direct → Still confusing (mirrors are hard)
  2. Use mirror_restore tool
  3. Read restored image → Success!
```

### Iteration 3 (Skill learned)
```
Task: New mirror clock
Strategy:
  1. Recognize: This is mirrored (from experience)
  2. Skip direct attempt (known limitation)
  3. Use mirror_restore
  4. Read → Success!
```

### Iteration 4 (Generalization)
```
Task: Mirror clock + rotation
Strategy:
  1. Use mirror_restore
  2. Still wrong (rotation issue detected)
  3. Generate rotation_fix tool
  4. Update skill: mirror_restore THEN rotate_fix
  5. Success!
```

## Summary

**Evolution Flow**:
```
Try Direct
  ↓ Fail
Analyze Why
  ↓
Generate Tool (if needed)
  ↓
Update Skill (how to use tool)
  ↓
Next Time: Skip known failures, use tools strategically
```

**Balance**:
- VLM is smart → Use it
- VLM has limits → Augment with tools
- Tools are for specific problems → Don't overuse
