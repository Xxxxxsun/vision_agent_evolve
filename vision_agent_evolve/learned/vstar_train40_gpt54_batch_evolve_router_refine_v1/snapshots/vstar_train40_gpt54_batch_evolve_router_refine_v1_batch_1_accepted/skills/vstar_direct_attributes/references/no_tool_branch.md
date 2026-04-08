<!-- Do-not-use-tool branch for unsupported or unnecessary-tool cases. -->

## No-tool / do-not-use branch

Use this branch when:
- The question requires **reading text, numbers, or labels**.
- The question asks for something **other than a visible localized attribute**.
- The target item is **so large and visually obvious** that localization is unnecessary.

Procedure:
1. Do not call the localization-color tool chain.
2. Answer only if the attribute is plainly visible without specialized localization.
3. If the task is outside visible localized color inspection, defer to the appropriate capability rather than forcing this SOP.

Warning:
- Do not invoke TextToBbox or RegionAttributeDescription for text-reading tasks or unrelated reasoning tasks.
