---
name: chartqa_arithmetic
description: "execute_python usage guide for ChartQA calculations"
level: low
---

# Arithmetic — execute_python Usage Guide

## When to Use execute_python
- Difference between two values: always compute, do not eyeball
- Sum or total across multiple bars/slices: use python
- Ratio or percentage change: use python
- Maximum or minimum across many values: either read directly or use python if values are close

## When NOT to Use execute_python
- The answer is a single directly-readable value from the chart — just read it
- Simple comparison where one value is obviously larger — state it directly
- The question asks for a label (category name, legend entry) — read it as text

## Correct Pattern

```python
# Extract the values first (write what you read from the chart)
value_a = 45.3   # read from the chart for category A
value_b = 28.7   # read from the chart for category B

# Then compute
difference = value_a - value_b
print(difference)  # always print so the result appears in output
```

## Common Calculation Templates

```python
# Percentage change
old_value = 120
new_value = 150
pct_change = (new_value - old_value) / old_value * 100
print(round(pct_change, 1))

# Sum across categories
values = [34, 28, 19, 42, 15]
print(sum(values))

# Ratio
part = 35
total = 100
ratio = part / total
print(round(ratio, 2))

# Difference
a = 67.5
b = 43.2
print(round(a - b, 1))
```

## Failure Checks
- Never pass an estimated value to execute_python — read the exact number from the chart first.
- Always use `print()` to see the output — silent assignments produce no result.
- Check units before arithmetic: if values are in thousands, the result is also in thousands.
- Round appropriately: ChartQA typically expects 1–2 decimal places or integer answers.
