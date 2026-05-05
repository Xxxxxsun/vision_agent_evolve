---
name: chartqa
description: "Minimal ChartQA skill — read exact values directly, python for arithmetic only"
level: mid
tool_names: ["execute_python"]
final_answer_policy: direct_answer
applicability_conditions: "Use for ChartQA questions about chart values, comparisons, or text labels."
---

# ChartQA

Read values **directly from the original image** — do not zoom or crop.
Call `execute_python` (with `print()`) only to verify arithmetic after reading values.
Return the number or short text directly — no extra words, no units, no explanation.
