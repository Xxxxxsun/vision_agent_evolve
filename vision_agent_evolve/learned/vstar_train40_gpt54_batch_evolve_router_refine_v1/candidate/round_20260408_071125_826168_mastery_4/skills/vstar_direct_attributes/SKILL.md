---
name: vstar_direct_attributes
description: "Route direct visible-attribute color questions to a localization-first tool branch when the named target is a small or person-attached object, and avoid tooling for non-visual-text or clearly unnecessary cases."
level: mid
depends_on: []
applicability_conditions: "Applies to multiple-choice direct-attribute questions asking for the visible color of a named object, accessory, or clothing item, especially when the target may be small, attached to a person, or easy to miss without region isolation; does not apply when the task depends on reading text, numbers, or labels, when the asked attribute is not a visible localized attribute, or when the target is so large and obvious that localization is unnecessary."
        ---

## Router
- If the question asks for the **color of a named visible item** and correct answering likely requires **isolating a specific region first**, follow [references/tool_branch.md](references/tool_branch.md).
- If the question depends on **reading text/numbers/labels**, asks for a **non-local or non-visible attribute**, or the target is **extremely obvious and large enough that localization is unnecessary**, follow [references/no_tool_branch.md](references/no_tool_branch.md).
- Do **not** answer from a casual global impression when the target is small, person-attached, or visually ambiguous; prefer the tool branch in those cases.
