# Third-Stage Mastery Refactor

This document summarizes the changes made to the third stage of the evolution pipeline.

## Goal

The original third stage behaved like another round of generic skill rewriting:

- generate a skill
- test it on a subset
- keep it if the score improved

That loop could improve accuracy, but it did not explicitly learn:

- when a tool should be used
- when a tool should not be used
- which tool chains are stable
- what the upper and lower bounds of a tool really are

The refactor turns stage three into a **tool mastery phase**.

## What Changed

### 1. Mastery is now a separate reasoning phase

The subset loop now runs an explicit mastery step before final skill materialization.

Instead of directly accepting a new SOP, the loop now:

- proposes several candidate tool-usage strategies
- evaluates them on a focused mastery case set
- measures each strategy by:
  - coverage
  - precision
  - score delta
- selects the best strategy
- distills the final skill from the evaluated strategy profile

This means the final skill is no longer the primary learned object. It is now the distilled result of a mastery evaluation process.

### 2. New mastery data structures were added

The evolution system now stores structured mastery artifacts:

- `MasteryStrategyCandidate`
- `MasteryEvalResult`
- `MasteryProfile`

These objects capture:

- tool sequence
- positive trigger conditions
- negative trigger conditions
- supported cluster patterns
- failure cluster patterns
- success cases and failure cases
- best chain patterns and bad chain patterns

This makes stage three analyzable instead of only score-driven.

### 3. Training memory now includes tool-boundary knowledge

`FamilyMemory` and digest payloads now carry mastery information.

That means later rounds can see:

- which mastery strategies were already tested
- which tools were useful for a family
- where those tools failed

This changes third-stage evolution from stateless prompt rewriting into accumulated tool-usage profiling.

### 4. Final skills are distilled from mastery profiles

The generator now has a dedicated mastery distillation path.

The final `SKILL.md` is produced from the selected mastery profile, not directly from a single family prompt.

As a result, the final skill is expected to encode:

- when to invoke a tool
- when to avoid a tool
- how to chain tools
- when to fall back to direct answering

### 5. A clean comparison baseline was added

To evaluate stage three more scientifically, the runner now supports a new frozen setting:

- `preset_tools_only`

This setting:

- exposes built-in tools
- does not load evolved skills
- does not force tool use

This makes it possible to compare:

- `direct_vlm`
- `preset_tools_only`
- `frozen_inference` (tools + evolved skill)

That comparison is important for answering whether mastery actually teaches better tool usage.

## Supporting Runtime Changes

### Frozen evaluation resume was improved

Frozen evaluation resume now:

- skips only healthy existing records
- reruns bad records with runtime errors or empty answers

This is important because long-running val jobs can now be recovered without redoing the whole run.

### Learned tool execution was isolated from workspace artifact noise

The learned tool runtime now executes relative to the tool directory instead of the repository root.

This prevents unrelated `artifacts/` files from polluting tool execution tests and artifact normalization.

## Main Files Touched

The core third-stage changes are centered in:

- `evolution/subset_loop.py`
- `evolution/roles.py`
- `evolution/types.py`
- `evolution/structured_runner.py`
- `evolution/loop.py`

The comparison baseline and recovery support also touched:

- `scripts/run_structured_experiment.py`
- `scripts/eval_structured_frozen.py`
- `tools/dynamic_loader.py`

## Practical Effect

After this refactor, stage three is no longer just:

- "write a better skill and keep it if the train subset score goes up"

It is now:

- "probe the tool's usage boundary"
- "learn the best trigger and anti-trigger conditions"
- "distill a mastery policy from those evaluations"

That is the intended scientific role of the third stage going forward.
