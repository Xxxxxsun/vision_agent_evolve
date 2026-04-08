<!-- Skip this mastery or avoid tool use when the task is out of scope or the answer is already visually obvious. -->

## No-tool / do-not-use branch

### Use this branch when
- The question is not really a localized color lookup.
- The evidence requires reading text, counting, non-color attribute recognition, or multi-step relational reasoning.
- The target object and its color are already plainly visible and unambiguous without zoomed inspection.

### Procedure
1. If out of scope for localized color lookup, do not invoke this mastery.
2. If in scope but trivially obvious, answer directly without tool use.
3. If uncertainty remains after a glance and the task is still a localized color question, switch back to [references/tool_branch.md](references/tool_branch.md).

### Guardrails
- Do not force tool use on every direct-attribute question.
- Do not use this mastery for generic scene questions with no clearly localized color target.
