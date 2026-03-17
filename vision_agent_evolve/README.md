# Vision Agent Evolve

A self-evolving visual agent that learns to solve vision puzzles through autonomous tool and skill generation.

## Overview

**Core Philosophy**: When the agent fails on a puzzle, it:
1. **Analyzes why it failed** - with **visual context** (sees original image + tool outputs)
2. Generates tools (code) or skills (strategies) to address the gap
3. Validates the new capability
4. Keeps it if it helps, discards if not
5. Repeats until success or gives up

**🔥 Key Feature: Visual Failure Analysis**

Unlike traditional text-only analysis, our AnalyzerDecider can **see** what went wrong:
- 📸 Original input image
- 🖼️ Tool-generated artifacts (processed images)
- 🔍 Direct visual comparison to identify issues

This enables much more accurate failure diagnosis. See [docs/VISUAL_ANALYSIS.md](docs/VISUAL_ANALYSIS.md) for details.

**Key Improvements over Original**:
- **2-3 LLM calls per iteration** (vs 8+ in original)
- **2 roles instead of 10** (AnalyzerDecider + Generator)
- **~2000 lines total** (vs 10,000+ in original)
- **Single-case focus** (solves one puzzle completely before moving on)
- **Enhanced skills** (strategic guides, not just usage manuals)

## Quick Start

### Installation

```bash
cd vision_agent_evolve

# Install dependencies
pip install -e .

# Or install dev dependencies
pip install -e ".[dev]"
```

### Configuration

Set environment variables for your VLM:

```bash
export VLM_BASE_URL="http://localhost:8000/v1"  # or OpenAI API
export VLM_API_KEY="your-api-key"
export VLM_MODEL="gpt-4o"  # or your model name
```

### Run on Single Example

**Evolution Mode** (self-improves until solved):
```bash
.venv/bin/python run.py --mode evolve --example datasets/mira/example_001.json --max-attempts 10
```

**Test Mode** (single run with current capabilities):
```bash
.venv/bin/python run.py --mode test --example datasets/mira/example_001.json
```

### Use Tools Directly

```bash
# Restore mirrored clock
python -m tools mirror_clock restore input.png output.png

# Answer clock question
python -m tools mirror_clock answer image.png "What time is shown?"
```

## Project Structure

```
vision_agent_evolve/
├── core/                   # Agent engine
│   ├── agent.py           # ReAct agent
│   ├── vlm_client.py      # VLM client
│   ├── types.py           # Data contracts
│   └── parser.py          # Response parser
│
├── skills/                 # Skill system
│   ├── base.py            # Skill class
│   ├── loader.py          # Discovery & loading
│   ├── renderer.py        # Render to prompt
│   └── library/           # Skill documents
│       ├── foundation/    # Universal skills
│       └── mirror_clock/  # Task-specific
│
├── tools/                  # Tool system
│   ├── base.py            # Tool interface
│   ├── registry.py        # Tool registry
│   ├── __main__.py        # CLI entry
│   └── implementations/   # Tool code
│       ├── shared/        # Reusable modules
│       └── mirror_clock/  # Task-specific tools
│
├── evolution/              # Self-evolution
│   ├── loop.py            # Main loop
│   ├── roles.py           # AnalyzerDecider + Generator
│   ├── validator.py       # 3-stage validation
│   └── store.py           # Capability storage
│
├── learned/                # Generated capabilities
│   ├── tools/             # Generated tools
│   ├── skills/            # Generated skills
│   └── evolution_log.jsonl
│
├── datasets/               # Example datasets
├── program.md             # Human guidance (editable!)
├── run.py                 # Main entry
└── README.md              # This file
```

## How It Works

### Evolution Loop

```
For each puzzle:
  Attempt 1-N (max 10):
    1. Try to solve with current capabilities
    2. If solved → Done ✓
    3. If failed:
       a. Analyze failure (1 LLM call)
       b. Decide: tool/skill/both/give_up
       c. Generate capability (1-2 LLM calls)
       d. Validate (3 stages):
          - Syntax check
          - Origin case test (must pass!)
          - Regression test (optional)
       e. If valid → KEEP (promote)
       f. If invalid → DISCARD (try again)
```

### Roles (Simplified from 10 to 2)

**1. AnalyzerDecider** (1 LLM call)
- Input: Failed attempt, current capabilities
- Output: Root cause + Next action (tool/skill/both/give_up)
- Replaces: Original Analyzer + Decider

**2. Generator** (1-2 LLM calls)
- Input: Failure analysis
- Output: Tool code or Skill document
- Replaces: Original ToolGenerator + SkillGenerator + Reviewer

### Validation (Simplified from 6 to 3 stages)

1. **Static**: Syntax check (AST parse)
2. **Origin**: Does it solve the original failed case? (Critical!)
3. **Regression**: Does it break previously solved cases? (Optional)

### Skills vs Tools

| Aspect | Skill | Tool |
|--------|-------|------|
| Format | Markdown document | Python code |
| Purpose | Guide strategy | Execute operations |
| Example | "When to restore clock" | `mirror_clock_restore.py` |
| Validation | Document structure | Syntax + Runtime |

## Example Dataset Format

Create `datasets/mira/example_001.json`:

```json
{
  "id": "mirror_clock_001",
  "problem_id": "mirror_clock",
  "prompt": "This is what a clock looks like in a mirror. What time will it be in 1 hours and 40 minutes?",
  "answer": "04:10",
  "image": "datasets/mira/images/mirror_clock_001.png"
}
```

## Human Guidance

Edit `program.md` to guide the evolution:

```markdown
## Current Focus
- Focus on mirror clock problems first
- Try CV-only before VLM

## Strategy Adjustments
- If restoration fails → try different flip/rotation
- If VLM gives wrong time → add validation step
```

## Monitoring Progress

### Check learned capabilities
```bash
ls -lh learned/tools/
ls -lh learned/skills/
```

### View evolution log
```bash
tail -20 learned/evolution_log.jsonl | jq
```

### See what's being tried
Watch the console output during evolution - it shows:
- Each attempt
- Analysis results
- Generation progress
- Validation outcomes
- Keep/discard decisions

## Comparison with Original Glue_SWE

| Metric | Original | This Project | Improvement |
|--------|----------|--------------|-------------|
| Code size | 10,000 lines | ~2,000 lines | -80% |
| LLM calls/iter | 8+ | 2-3 | -70% |
| Roles | 10 | 2 | -80% |
| Validation stages | 6 | 3 | -50% |
| Largest file | 2,185 lines | <200 lines | -90% |
| Focus mode | Batch processing | Single-case until solved | New! |

## Design Principles

1. **Simplicity > Completeness**: 50 lines that work > 500 lines that don't
2. **Fail Fast**: Quick validation catches bad ideas early
3. **No Over-Engineering**: Generate exactly what's needed
4. **Human Control**: Edit `program.md` to guide exploration
5. **Reproducible**: Full git history + evolution log

## Extending

### Add a New Tool

1. Create `tools/implementations/<name>/<tool>.py`:
```python
from core.types import ToolResult
from tools.base import Tool

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "What it does"

    def run(self, **kwargs) -> ToolResult:
        # Implementation
        return ToolResult(status="ok", answer="result")
```

2. Add to `tools/__main__.py` dispatcher

3. Create skill document in `skills/library/<name>/SKILL.md`

### Add a New Skill

Create `skills/library/<name>/SKILL.md`:
```markdown
---
name: my_skill
description: "Brief description"
level: high
depends_on: [vision_analysis]
---

# My Skill

## When to Use
...

## Strategy
...
```

## Troubleshooting

**Agent can't find tools**
- Make sure you're in the project root when running
- Check `python -m tools` works

**VLM connection fails**
- Verify `VLM_BASE_URL`, `VLM_API_KEY`, `VLM_MODEL` are set
- Test with `curl $VLM_BASE_URL/models`

**Generated code has syntax errors**
- Generator might need better prompts
- Check `evolution/roles.py` prompts
- Try simpler examples first

**Evolution gets stuck**
- Check `program.md` for guidance
- Reduce `max_attempts`
- Try giving it an easier example first

## License

MIT

## Credits

Inspired by:
- **Glue_SWE** - Original VLM agent + self-evolution framework
- **Autoresearch** (Andrej Karpathy) - Fixed budget, simple decisions, minimal scope
