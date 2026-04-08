---
name: vstar_direct_attributes
description: "Route direct visible color-attribute questions on localized objects or clothing to a localized color inspection workflow, with a no-tool fallback only when the attribute is already unmistakably clear."
level: mid
depends_on: []
applicability_conditions: "Applies to multiple-choice direct visual attribute questions asking for the color of a named object, accessory, or clothing region that must be visually localized; especially for person-associated items or small/cluttered regions. Do not apply when the task is about reading text, counting, non-color attributes, or broader relational/scene reasoning. Avoid tool use when the target color is already clearly and confidently visible without local inspection."
        ---

## Router
- If the question asks for a directly visible **color** of a specific named object/clothing/accessory and the evidence is localized, follow [references/tool_branch.md](references/tool_branch.md).
- If the evidence is text-like, requires counting, non-color attributes, or multi-object/scene reasoning, do **not** use this mastery; follow [references/no_tool_branch.md](references/no_tool_branch.md).
- If the target object and its color are already unambiguous at a glance, skip tool use and follow [references/no_tool_branch.md](references/no_tool_branch.md).
