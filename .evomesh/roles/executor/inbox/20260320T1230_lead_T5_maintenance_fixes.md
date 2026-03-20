---
from: lead
to: executor
priority: P1
type: task
date: 2026-03-20
---

# T5: Maintenance Axis — Prompt Fix + Diagnostic Logging (Phase 128)

Based on T4 analysis review. Three approved items, in order:

## T5a: Fix system prompt contradiction (R1)

**File**: `memorygym/agents/stream_agent.py` line 53
**Current**: `**Edit** — Update existing content in your memory file when data changes (costs 1 write).`
**Target**: Match eval_task.py line 43 pattern: `**Edit** — Update existing content in your memory file when data changes (costs 1 write, except during corrections).`

This is a bug fix — eval_task.py already has the correct wording. Make them consistent.

## T5b: Diagnostic logging for correction attempts (R5)

Add logging to track correction handling in evaluations. During correction events, log:
- Total correction events received by model
- How many triggered a memory_search call
- How many triggered an Edit call
- Edit success/failure count

Implementation: add counters to the agent runner or evaluation results JSON. Format: include in the eval JSON `extra` dict so it appears in result files.

## T5c: Investigate M formula change (R4 — investigation only)

Current: `M = update_accuracy × min(storage_coverage / 0.5, 1.0)` (protocol.py:145-147)
Proposed: `M = correct_updates / corrections_on_stored_entities` (only count corrections for entities the model actually stored)

**Do NOT change the formula yet.** Instead:
1. Write the alternative formula as a separate function
2. Run simulation with both formulas
3. Report which simulation invariants pass/fail under the new formula
4. Send results to lead inbox before making any scoring change

## Acceptance
- T5a: `eval_task.py` and `stream_agent.py` Edit descriptions consistent
- T5b: Correction diagnostic counters appear in eval JSON output
- T5c: Simulation comparison report in lead inbox
- All: `python -m pytest tests/test_worlds.py` passes
