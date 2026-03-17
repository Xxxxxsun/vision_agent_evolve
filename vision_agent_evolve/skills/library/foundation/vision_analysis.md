---
name: vision_analysis
description: "Foundation skill for analyzing visual content"
level: foundation
depends_on: []
---

# Vision Analysis

## Purpose
This foundational skill guides you in systematically analyzing visual content before taking actions.

## When to Use
- **Always** inspect attached images before deciding on tools
- When the task involves understanding visual elements
- Before running any image processing commands

## Analysis Checklist

### 1. Image Type Recognition
- Is this a photograph, diagram, screenshot, or artistic rendering?
- Is it color or grayscale?
- What is the approximate resolution/quality?

### 2. Main Subject Identification
- What is the primary subject or object?
- Are there multiple subjects?
- What is the context or setting?

### 3. Visual Features
- Colors: dominant colors, color scheme
- Shapes: geometric shapes, patterns
- Text: any visible text or labels
- Spatial relationships: positions, orientations

### 4. Task-Specific Elements
- If clock: hand positions, numbers visible
- If diagram: labels, connections, flow
- If puzzle: pieces, patterns, missing elements

## Output Format

After analysis, state your observations concisely:

```
Image Analysis:
- Type: [photograph/diagram/etc]
- Subject: [main subject]
- Key features: [list 2-3 most important features]
- Relevant for task: [what matters for solving this task]
```

## Common Pitfalls

❌ **Don't**: Jump to tools without understanding the image
❌ **Don't**: Make assumptions without visual evidence
❌ **Don't**: Ignore small details that might be crucial

✅ **Do**: Describe what you actually see
✅ **Do**: Note uncertainties or ambiguities
✅ **Do**: Connect observations to the task goal
