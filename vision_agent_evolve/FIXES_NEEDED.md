# Vision Agent Evolve — Fixes Needed

## Background

This is a self-evolving VLM agent system. When an agent fails a task, it:
1. Analyzes the failure (AnalyzerDecider)
2. Generates a tool (Python script) and/or a skill (Markdown guidance doc)
3. Validates the tool by running the agent again with the tool available
4. If validation passes, promotes tool/skill to `learned/`
5. Retries the task with the new capabilities

The test case is a mirrored clock image (`datasets/mira/images/2.png`). The correct answer is **3:20** (actual time is 7:10; 7:10 + 8h10m = 3:20).

We confirmed that kimi-k2.5 reads the **flipped** (un-mirrored) clock correctly as 7:10 in a direct API call. So the entire evolution machinery just needs to work correctly.

---

## Bug 1 (CRITICAL): Tool-generated images are never sent back to the VLM

**File:** `core/agent.py`

**Problem:**
The agent is a VLM agent. The original task image is sent visually in the first turn. When a tool runs (e.g., flips the image and saves it to `artifacts/flipped.png`), the observation is only passed as **text** to the next turn. The flipped image is never sent back to the VLM visually. So the VLM cannot see the processed image.

**Current code (line ~133):**
```python
messages.append({"role": "user", "content": self.parser.format_observation(observation)})
```

`format_observation` returns a plain string. Image artifact paths mentioned in `ARTIFACTS: path` are never embedded as visual content.

**Fix:**
After running bash, check if `observation` contains `ARTIFACTS: path1.png, path2.png`. For each valid image file path found, embed the image as `image_url` content in the user message (same base64 format as the initial image). This way the VLM can actually SEE the processed image in the next turn.

The `_extract_artifacts` method already parses `ARTIFACTS:` lines from observation text. Use its output to build a multimodal message.

Example multimodal message structure:
```python
[
    {"type": "text", "text": "Observation:\n<tool output text>"},
    {"type": "text", "text": "\n[Tool output image: flipped.png]"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,<base64data>"}}
]
```

Only embed images that actually exist on disk. Cap at 3 images to avoid token explosion. If no image artifacts exist, fall back to plain text (current behavior).

---

## Bug 2 (CRITICAL): Tool is not available to agent during validation

**File:** `evolution/validator.py`

**Problem:**
During tool validation, `validate_tool()` writes the generated tool to `artifacts/temp_tool.py` (a temp location). But `python -m tools` only discovers tools from `learned/tools/*.py`. So when the validation agent tries to call the tool by name, it gets "Unknown tool" and falls back to manual reasoning.

**Fix:**
Write the tool to `learned/tools/<tool_name>.py` **before** running the validation agent. If validation fails, delete the file afterwards. If validation passes, the file stays (already promoted).

```python
# Before running agent:
tool_path = project_root / "learned" / "tools" / f"{proposal.name}.py"
tool_path.write_text(proposal.code)

# If validation fails:
tool_path.unlink(missing_ok=True)
```

---

## Bug 3 (CRITICAL): Agent doesn't know which tools are available

**File:** `evolution/loop.py`, method `_create_agent()`

**Problem:**
The agent's system prompt contains only:
```
Use: python -m tools <tool_name> [args]
```
There is no list of actual available tools. The agent has to guess tool names, and always guesses wrong (e.g., invents `mirror_restore`, `view_image`, etc. that don't exist).

**Fix:**
Before creating the agent, scan `learned/tools/*.py` and build a list of available tools with their names and usage examples. Include this list explicitly in `tool_definitions`. Read the `.json` metadata files (if present) for description and usage. If no metadata, use a default usage pattern.

Example output:
```
Use: python -m tools <tool_name> [args]

Available learned tools:
  - mirror_clock_solver: Flips mirror clock image and returns the time | usage: python -m tools mirror_clock_solver <image_path>
```

---

## Bug 4: Skill is generated before tool validation result is known

**File:** `evolution/loop.py`

**Problem:**
When `next_action = "generate_both"`, the original code generated both tool and skill simultaneously, then validated the tool. If the tool failed validation, the skill was still promoted but referenced a non-existent tool.

**Fix:**
Generate and validate the tool first. Only then generate the skill, passing `promoted_tool` (the actual validated tool, or `None` if it failed). The skill generator should only reference tools that are confirmed promoted.

Correct order:
1. Generate tool
2. Validate tool → if passes, set `promoted_tool = tool_proposal`; if fails, set `promoted_tool = None`
3. Generate skill (passing `promoted_tool`)
4. Validate and promote skill

---

## Bug 5: Success check uses substring match — "3:20" matches inside "13:20"

**Files:** `evolution/loop.py` (`_check_success`) and `evolution/validator.py` (`_check_answer`)

**Problem:**
```python
if expected in actual:  # "3:20" in "...13:20..." → True (wrong!)
    return True
```

**Fix in `_check_success` (loop.py):**
Use an LLM judge. Send both the expected answer and the agent's full response to the LLM and ask it to determine if the agent answered correctly. This handles semantic equivalence (3:20 = 15:20 = 3:20 PM) and avoids substring false positives.

```python
prompt = f"""Expected answer: {case.gold_answer}
Agent's answer: {result.final_answer}
Did the agent get the correct answer? Reply with only CORRECT or INCORRECT."""
response = llm.chat(...)
return "INCORRECT" not in response.upper() and "CORRECT" in response.upper()
```

**Fix in `_check_answer` (validator.py):**
Use word-boundary regex:
```python
import re
return bool(re.search(r'(?<!\d)' + re.escape(expected_norm) + r'(?!\d)', actual_norm))
```

---

## Bug 6: Skill generator invents non-existent tools

**File:** `evolution/roles.py`, `generate_skill()`

**Problem:**
When generating a skill without a specific promoted tool to reference, the LLM invents tool names like `coordinate_extraction`, `angle_calculation`, `mathematical_conversion` that don't exist in `learned/tools/`.

**Fix:**
In the skill generation prompt, explicitly state:
- If a tool was promoted: "You MUST reference ONLY this tool: `<tool_name>`. Usage: `python -m tools <tool_name> <image_path>`"
- If no tool was promoted: "No tool is available. Write a reasoning-only strategy. Do NOT invent or reference any tool names."

---

## Summary of files to change

| File | Changes |
|------|---------|
| `core/agent.py` | Build multimodal observation messages when tool outputs image artifacts |
| `evolution/validator.py` | Write tool to `learned/tools/` before validation; delete on failure; use word-boundary regex in `_check_answer` |
| `evolution/loop.py` | List available tools in agent's system prompt; generate skill AFTER tool validation; use LLM judge in `_check_success` |
| `evolution/roles.py` | Constrain skill generator to only reference confirmed promoted tools |

---

## Verification

After all fixes, the expected behavior for the mirror clock test case is:

1. **Attempt 1**: Agent tries directly → fails (reads wrong time)
2. **Evolution**: Analyzer identifies VLM can't read mirrored clocks reliably
3. **Tool generated**: A tool that horizontally flips the image and saves to `artifacts/`
4. **Validation**: Agent calls `python -m tools <tool_name> datasets/mira/images/2.png` → tool flips image → `ARTIFACTS: artifacts/flipped.png` in output → **flipped image is sent back to VLM visually** → VLM reads 7:10 correctly → 7:10 + 8:10 = 3:20 ✓ → validation passes
5. **Attempt 2**: Agent uses the promoted tool → sees flipped clock → answers 3:20 ✓
