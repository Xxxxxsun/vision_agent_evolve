<!-- Do-not-use-extra-tools branch for obvious, directly localizable object pairs. -->

## No-tool / do-not-use-extra-tools branch

Use this branch when:
- both queried objects are visually obvious
- the objects are uniquely identifiable from the image without extra scene grounding
- speed and compactness are preferred

Avoid this branch when:
- object names are ambiguous or may have synonyms
- the scene is cluttered enough that candidate entities may be confused
- you are not confident you have identified both referenced objects

Procedure:
1. Visually localize both named objects directly in the image.
2. Compare their horizontal positions in the image plane.
3. Answer only after explicitly determining which object is farther left/right.

Guardrails:
- Do not answer from language priors alone.
- Do not use fixed image-coordinate assumptions.
- If direct localization is not confident, switch to [references/tool_branch.md](references/tool_branch.md).
