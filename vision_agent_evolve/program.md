# Vision Agent Evolution - Program Guide

## Mission
Autonomously solve vision puzzles by generating and learning tools and skills.

## Current Focus
- **Dataset**: MIRA vision puzzles
- **Priority**: Mirror clock problems → Other puzzle types
- **Goal**: 70%+ solve rate with minimal code bloat

---

## Strategy Guidelines

### Tool Generation Philosophy

**Prefer Simple Over Complex**
- ✅ 50-line focused tool > 500-line monolithic tool
- ✅ Reuse `tools/implementations/shared/` modules
- ✅ One tool = one clear responsibility

**CV First, VLM Second**
- Try computer vision (CV) only approaches first
- Use VLM only when reasoning/interpretation is needed
- Hybrid: CV preprocessing → VLM reasoning

**Quality Gates**
- Must pass syntax check (AST parse)
- Must solve the origin case
- Keep code under 150 lines per tool
- Use type hints and docstrings

### Skill Generation Philosophy

**Be Specific and Actionable**
- Describe exact steps, not vague advice
- Include concrete bash commands
- Show expected outputs

**Include Failure Handling**
- List common errors and solutions
- Provide debugging tips
- Explain when to give up

**Structure Matters**
```markdown
## When to Use
(clear conditions)

## Strategy
1. Step one
2. Step two
(concrete, numbered steps)

## Common Failures
| Error | Solution |

## Example
(complete walkthrough)
```

**Layering**
- Foundation skills: universal (vision_analysis, reasoning)
- High-level skills: task-specific strategies
- Mid/Low-level skills: tactical execution

---

## Decision Rules

### When to Generate Tool
- Need new image processing capability
- Need computation or transformation
- Current tools don't cover this operation

### When to Generate Skill
- Strategy is unclear
- Agent is using tools incorrectly
- Need better guidance on when/how to act

### When to Generate Both
- New tool needs usage guidance
- Tool + skill can solve the problem together

### When to Give Up
- After 10 failed attempts on same case
- Syntax errors persist after 3 generation attempts
- Case requires external knowledge not in image
- Task is fundamentally unsolvable

---

## Constraints

### Code Size Limits
- Tools: **<150 lines** (hard limit)
- Skills: **<100 lines** of content
- Shared modules encouraged to stay under limits

### LLM Call Budget
- Max **3 LLM calls per iteration**:
  1. AnalyzerDecider
  2. Generator (tool)
  3. Generator (skill) - optional

### Time Budget
- Agent: **20 turns max** per attempt
- Validation: **60s timeout** per test

### Memory Constraints
- Keep **<5 variants** of same tool
- Archive old versions if new one is better
- Prefer updating skills over creating new ones

---

## Success Metrics

### Primary Goals
- **Solve rate**: >70% of dataset
- **Iterations to solve**: <5 average
- **Code bloat**: <2000 total lines in learned/

### Secondary Goals
- **Tool reuse**: >50% of tools used in 2+ cases
- **Skill clarity**: Human-readable and actionable
- **Validation pass rate**: >60% of generated tools

---

## Notes & Observations

*This section is editable by humans. Add learnings, adjust strategy, note patterns.*

### 2026-03-13 - Project Start
- Initial focus: mirror clock puzzles
- Starting with CV-only approach for restoration
- VLM for answering time questions

### Learnings (to be filled)
- [ ] Which types of puzzles are easiest?
- [ ] What's the most common failure mode?
- [ ] Do generated tools actually get reused?
- [ ] How often do skills need updating?

### Strategy Adjustments (to be made)
- [ ] If CV-only fails repeatedly → switch to VLM-first
- [ ] If tool generation fails → try simpler templates
- [ ] If skills are ignored → make them more prominent

---

## Debug Commands

If evolution seems stuck:

```bash
# Check what's been learned
ls -lh learned/tools/
ls -lh learned/skills/

# Review evolution log
tail -20 learned/evolution_log.jsonl | jq

# Test a specific tool manually
python -m tools mirror_clock restore test_image.png

# Test agent with current capabilities
python run.py --mode test --example datasets/mira/example_001.json
```
