<!-- Direct visual comparison branch for easy left/right cases where tools are unnecessary. -->

## No-tool branch

Use this branch when both named objects are clearly visible and easy to localize directly.

### Positive triggers
- Each queried object is obvious in the image.
- There is little or no ambiguity about which instances are referenced.
- The answer can be determined by straightforward horizontal comparison.

### Negative triggers
- Object names are ambiguous, unusual, or likely to match multiple regions.
- Extra scene context is needed to identify the intended objects.
- The scene is cluttered enough that direct localization is uncertain.

### Procedure
1. Identify the two referenced visible objects directly.
2. Compare their horizontal positions in the image.
3. Answer with the object that is on the left or right as requested.

### Do-not-use note
- Do not force the tool chain for easy, already-clear cases.
- Do not answer if object identity is uncertain; route to `references/tool_branch.md` instead.
