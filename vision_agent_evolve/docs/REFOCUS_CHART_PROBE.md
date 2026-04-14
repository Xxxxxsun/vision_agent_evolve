# Refocus_Chart Probe Report

## Direct VLM Failure Modes

- `other_wrong`: `80`
- `correct`: `557`
- `truncated_output`: `21`
- `overlong_reasoning_or_truncation`: `100`
- `ratio_or_time_format_confusion`: `57`
- `boolean_polarity_error`: `2`
- `contains_expected_but_extra_text`: `8`
- `empty_answer`: `1`

## Manual Skill + Tool Failure Modes

- `tool_guided_wrong_answer`: `168`
- `correct`: `410`
- `empty_answer`: `223`
- `contains_expected_but_extra_text`: `9`
- `boolean_polarity_error`: `5`
- `ratio_or_time_format_confusion`: `11`

## Direct vs Manual Quadrants

- `direct_wrong__manual_wrong`: `185`
- `direct_correct__manual_correct`: `326`
- `direct_wrong__manual_correct`: `84`
- `direct_correct__manual_wrong`: `231`

## Probe Reading

- `direct_vlm` is hurt mainly by overlong reasoning, truncation, and ratio/format confusion rather than pure visual blindness.
- `manual skill + tool` is hurt mainly by `empty_answer` and `tool_guided_wrong_answer`, which suggests the current handwritten SOP/tool orchestration is the main failure point.
- The dominant manual failure mode is not lack of tool access; it is using tools but failing to convert the resulting evidence into a correct short final answer.

## Sample Quadrant Cases

### `direct_wrong__manual_wrong`

- `00339007006077` `refocus_chart_chartqa_h_bar_count_or_total` expected=`5.95` direct=`16.55` manual=`16.55`
- `02534409005100` `refocus_chart_chartqa_h_bar_generic` expected=`Yes` direct=`To determine if the median value of all the bars is greater than 30, let's follow these steps:

1. **Identify the values` manual=`No`
- `03672594001226` `refocus_chart_chartqa_h_bar_generic` expected=`Yes` direct=`To determine if the average value of the Philippines and North America is greater than 2500 MW, let's follow these steps` manual=``
- `05810070001466_2` `refocus_chart_chartqa_h_bar_generic` expected=`1931` direct=`1.93 t` manual=`1.93 t`
- `10505` `refocus_chart_chartqa_h_bar_generic` expected=`2.13` direct=`62:2` manual=`The ratio of people who approve to those who disapprove about Putin's handling of Corruption is approximately 2.14:1.`

### `direct_correct__manual_correct`

- `00339007006077_2` `refocus_chart_chartqa_h_bar_generic` expected=`5.32` direct=`Libya (5.32%)` manual=`5.32%`
- `01001540004402_2` `refocus_chart_chartqa_h_bar_count_or_total` expected=`Finland` direct=`To determine which color bar shows the greatest meat consumer, let's analyze the image step by step:

1. **Identify the ` manual=`Finland`
- `01499440003158_2` `refocus_chart_chartqa_h_bar_generic` expected=`1` direct=`1 GPI` manual=`1 GPI`
- `01729694006399_2` `refocus_chart_chartqa_h_bar_generic` expected=`Pink` direct=`Pink/Magenta` manual=`The color representing China in the chart is pink.`
- `02534409005100_2` `refocus_chart_chartqa_h_bar_generic` expected=`Heart disease` direct=`The image shows a bar chart titled "Death rates through the 20th century, United States, 1966." It lists various causes ` manual=`Heart disease`

### `direct_wrong__manual_correct`

- `01001540004402` `refocus_chart_chartqa_h_bar_count_or_total` expected=`No` direct=`To answer this question, let's break it down step by step:

1. **Identify the values for each region:**
   - **Georgia:*` manual=`No, the sum of Georgia and Western Asia is not more than Finland.`
- `05705464003774_2` `refocus_chart_chartqa_h_bar_generic` expected=`0.1` direct=`Colombia's data shows that its government expenditure on pre-primary education was 0.` manual=`0.1%`
- `08263936005626` `refocus_chart_chartqa_h_bar_count_or_total` expected=`No` direct=`To answer this question, let's follow these steps:

1. **Identify the values for Milk and Cheese**:
   - Milk: 27.1 m²
 ` manual=`No`
- `10222` `refocus_chart_chartqa_h_bar_count_or_total` expected=`4` direct=`To answer this question, let's analyze the chart step by step:

1. **Identify the median age of "The Daily Show"**: The ` manual=`4`
- `10227` `refocus_chart_chartqa_h_bar_extrema` expected=`64` direct=`To analyze the difference between the maximum and minimum values for "right" and "wrong" decisions based on the provided` manual=`The difference between the maximum "Right decision" value (76) and the minimum "Wrong decision" value (12) is 64.`

### `direct_correct__manual_wrong`

- `01499440003158` `refocus_chart_chartqa_h_bar_comparison` expected=`0.08` direct=`0.08` manual=``
- `01729694006399` `refocus_chart_chartqa_h_bar_extrema` expected=`No` direct=`No` manual=`Based on the visual inspection of the chart, the two lowest bars are Armenia and Israel, both at 0%. The largest bar is `
- `03672594001226_2` `refocus_chart_chartqa_h_bar_extrema` expected=`North America` direct=`North America` manual=``
- `04214944001005` `refocus_chart_chartqa_h_bar_comparison` expected=`203` direct=`203` manual=``
- `05705464003774` `refocus_chart_chartqa_h_bar_count_or_total` expected=`5` direct=`5` manual=``
