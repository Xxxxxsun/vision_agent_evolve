---
name: hrbench
description: "Visual attention SOP for high-resolution image text/symbol reading — no tools"
level: mid
depends_on: ["vision_analysis", "reasoning"]
tool_names: []
final_answer_policy: option_letter
applicability_conditions: "Use for HRBench multiple-choice questions about local text, signs, symbols, numbers, or scene details."
---

# HRBench — Visual Attention

## Trigger
- The question asks about a specific piece of text, number, sign, symbol, or local visual detail in the image.
- The image is high-resolution with fine detail — the target may be small relative to the full scene.

## Procedure
1. Read the question carefully and identify exactly what target element is being asked about (a word, a number, a symbol, a color, etc.).
2. Determine where this element is likely located in the scene:
   - Outdoor: signs, labels, and text are often on buildings, vehicles, or street furniture.
   - Indoor: text appears on menus, labels, screens, boards.
   - Think about the typical position (edge, corner, center) based on scene context.
3. Direct your visual attention to that region of the image and read the target element as precisely as possible.
4. Cross-reference: confirm the element you found is the one the question asks about (not a nearby similar element).
5. Compare the read value against each answer option.
6. Return the matching option letter.

## Attention Strategy
- If the target location is uncertain, scan the image systematically: top-left → top-right → center → bottom-left → bottom-right.
- When multiple similar elements exist (e.g., several signs), use surrounding context to identify the correct one.
- For text: read character by character if the text is short; for longer text, focus on the key word the question references.
- For numbers: note all digits carefully; a single misread digit changes the answer.

## Failure Checks
- Do not confuse a nearby similar sign, symbol, or text for the target.
- Do not assume the most visible element is the one being asked — read the question again.
- After reading the target, verify it against the options before committing.
- Return only the option letter — do not return the raw text value.
