---
name: billiards_case_11_failure_lesson
description: "Failure lesson for handling trajectory-based billiards tasks when specific tools are unavailable."
level: low
depends_on: []
applicability_conditions: "When the task requires predicting a ball's trajectory on a billiards table and the agent lacks a pre-defined path-tracing tool."
kind: failure_lesson
---

## SOP
1. Recognize that the current task-family SOP was not sufficient for this example.
2. Helpful method: The image shows a standard billiards table with a blue ball and a green directional arrow. No tool-generated artifacts exist. The agent failed because it tried to use a tool that wasn't registered. Implementing the tool is the necessary step to solve the geometric path-tracing problem.
3. Common mistake: The agent attempted to call a non-existent tool 'billiards_path_tracer' instead of performing the geometric calculation or using a valid tool.
4. Next time, consider: A tool that performs geometric vector reflection calculation on the table coordinates.
