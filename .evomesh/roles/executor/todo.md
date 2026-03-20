# executor — 待办任务

## T5: Implement R1 + R5 from maintenance analysis — Priority: HIGH

**Background**: Lead reviewed T4 analysis. R1 and R5 approved (see `shared/decisions.md` D1). R2 rejected (prompt neutrality), R3/R4 deferred.

### T5a: Fix system prompt Edit cost contradiction (R1)

**File**: `memorygym/agents/stream_agent.py` around line 53.

**Change**: Update the Edit tool description to clarify that Edit is free during correction events. Example:
```
Edit — Update existing content (costs 1 write; free during correction events)
```

Do NOT add workflow examples or strategy hints. Only fix the factual description of tool cost behavior.

### T5b: Add correction diagnostic logging (R5)

**Where**: Evaluation flow where correction events are processed.

**What to log**: For each evaluation, track:
- Total correction events sent to model
- How many triggered a `memory_search` call
- How many triggered an `Edit` call
- How many Edits succeeded vs failed (old_text not found)

Include counts in the evaluation result JSON (under an `extras` or `diagnostics` key).

### Validation

After both changes:
1. `python -m pytest tests/test_worlds.py` must pass
2. `python -m pytest tests/ -q -m "not slow"` must pass
3. Verify simulation invariants still hold: all 9 strategies within expected bounds

### Deliverable
- Commit both changes (can be separate commits)
- Send ack to lead inbox when done

## Completed
- [x] T1: build_assistant_mask tests (5 tests, commit `ee817d0`)
- [x] T2: Training code commit (verified already committed by trainer)
- [x] T3: Edit reward dedup in env.py → `_edit_correction_reward` helper (commit `595a6de`)
- [x] T4: Maintenance axis analysis → `.evomesh/shared/maintenance_analysis.md`
