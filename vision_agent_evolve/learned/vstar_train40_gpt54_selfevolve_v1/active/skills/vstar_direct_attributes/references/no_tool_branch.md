<!-- Fast path for direct attribute questions when the referent and attribute are obvious without tool use. -->

## No-Tool Branch

### Use this branch when
- The question asks for a single directly visible attribute of a clearly referenced entity.
- The target is obvious at full-image scale.
- The requested attribute is visually unambiguous without localization.

### Do not use this branch when
- The object is small, cluttered, partially hidden, or easy to confuse with nearby items.
- You are uncertain about the target location or attribute.

### Procedure
1. Identify the named referent directly from the full image.
2. Read the requested attribute from the visible appearance.
3. Match it to the provided multiple-choice options.
4. If any uncertainty remains about localization or attribute reading, switch to [references/tool_branch.md](references/tool_branch.md).
