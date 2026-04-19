---
name: mathvista_mcq
description: "Branch detail for MathVista multiple-choice questions"
level: low
---

# MathVista — MCQ Branch

## Trigger
- The question provides labeled answer choices (A, B, C, D or similar).
- The final answer must be the matching option letter, not a raw number or word.

## Procedure
1. Read the answer choices first — they tell you the type and range of the expected answer.
2. Identify what the question is actually asking for (a value, a relationship, a category).
3. Extract the relevant quantities from the figure using zoom_image if needed.
4. Compute the result with execute_python if arithmetic is required.
5. Compare the result against the labeled choices:
   - For numeric answers: find the option whose value is closest to your computed result.
   - For categorical or relational answers: match the description to the correct option.
6. Return only the option letter in Final answer.

## Matching Strategy
- If choices are numeric and your result is between two options, pick the nearest one.
- If choices are expressions (e.g., "2x + 1"), evaluate them mentally or with execute_python to find which matches.
- If choices are descriptions ("increases", "decreases"), derive the direction from the figure.

## Failure Checks
- Never return the raw numeric result — always map to an option letter.
- Do not guess without inspecting the figure — use zoom if the relevant values are small.
- If two options look equally close, re-read the figure or re-compute more carefully.
- Check whether the question asks for an approximation or exact value before choosing.
