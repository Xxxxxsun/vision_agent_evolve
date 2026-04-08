---
name: vstar_direct_attributes
description: "Route directly visible single-attribute multiple-choice questions about a specifically named entity to either a no-tool quick read when obvious or a localization-first tool branch when the target is small, cluttered, or ambiguous."
level: mid
depends_on: []
applicability_conditions: "Applies when the question asks for one directly visible attribute of a clearly referenced object, accessory, garment, or person in a multiple-choice format, especially color; use the tool branch when the referent may need localization, and avoid this SOP for counting, reading text, multi-entity comparison, or inference-heavy questions."
        ---

## Router
1. Confirm the task is a single directly visible attribute lookup for a specifically named referent in a multiple-choice question.
2. If the target is obvious at full-image scale and the attribute is unambiguous, follow [references/no_tool_branch.md](references/no_tool_branch.md).
3. If the target may be small, embedded in clutter, visually confusable with nearby items, or not immediately localized, follow [references/tool_branch.md](references/tool_branch.md).
4. Do not use this SOP for counting, reading text, comparing several similar candidates, or questions requiring inference beyond direct visual inspection; follow [references/do_not_use_branch.md](references/do_not_use_branch.md).
