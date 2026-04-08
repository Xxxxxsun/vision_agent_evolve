<!-- Direct visual comparison branch for obvious two-object relative position questions where extra grounding is unnecessary. -->

## No-tool branch: direct visual comparison

**Use this branch when:**
- The question asks only whether one object is above/below or left/right of another.
- Both referenced objects are obvious and easy to identify directly in the image.
- The relation can be determined confidently by inspecting the two objects.

**Do not use this branch when:**
- Either object identity is ambiguous, uncommon, or easy to confuse.
- You are uncertain which visual instances correspond to the object names.
- The task requires counting, reading text, depth/front-behind reasoning, or more than a single binary relation.

**Procedure**
1. Locate the two named objects directly in the image.
2. Compare only their image-plane positions.
3. For above/below, decide which object is higher in the image; for left/right, decide which object is farther left.
4. Select the matching answer choice.

**Guardrails**
- Do not answer from typical real-world arrangements.
- Do not infer hidden depth relations.
- If direct inspection is not reliable, switch to `references/tool_branch.md`.
