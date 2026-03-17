---
name: reasoning
description: "Foundation skill for structured reasoning"
level: foundation
depends_on: []
---

# Structured Reasoning

## Purpose
Guide systematic problem-solving for vision tasks.

## Reasoning Framework

### 1. Understand the Goal
- What is the task asking for?
- What format should the answer be in?
- Are there any constraints or requirements?

### 2. Identify the Gap
- What do I know from the image?
- What information is missing?
- What tools or processing might help?

### 3. Plan Approach
- What's the simplest path to the answer?
- Should I try CV-only or use VLM?
- What intermediate steps are needed?

### 4. Execute Step-by-Step
- Perform one operation at a time
- Verify each step's output
- Adjust if results are unexpected

### 5. Validate Result
- Does the answer make sense?
- Does it match the expected format?
- Are there edge cases to check?

## Decision Trees

### When to use CV vs VLM?
- **CV-only**: Geometric transformations, known patterns, measurements
- **VLM**: Complex interpretation, ambiguous content, reasoning required
- **Hybrid**: CV preprocessing → VLM interpretation

### When to create intermediate artifacts?
- If the task requires multiple steps
- If verification is needed
- If debugging might be necessary

## Best Practices

✅ Start simple, add complexity only if needed
✅ Document your reasoning in thoughts
✅ Check outputs before using them in next steps
✅ Be explicit about uncertainties
