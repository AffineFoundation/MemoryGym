# executor — Tasks

## T5: Maintenance Axis — Prompt Fix + Diagnostic Logging (Phase 128, P1)

See inbox `20260320T1230_lead_T5_maintenance_fixes.md` for full spec. Three sub-tasks:

- **T5a**: Fix stream_agent.py Edit prompt to say "except during corrections" (matching eval_task.py). Do NOT add workflow examples or strategy hints — only fix factual tool cost description.
- **T5b**: Add correction diagnostic counters to eval JSON output (total corrections, memory_search count, Edit count, Edit success/fail)
- **T5c**: Investigate alternative M formula — simulation comparison only, do NOT change scoring. Send results to lead inbox.

Acceptance: test_worlds.py passes, consistent prompts, diagnostic data in eval JSON.

## Completed
- [x] T1: 5 unit tests for build_assistant_mask (commit `ee817d0`)
- [x] T2: Training code committed
- [x] T3: _find_subseq extraction + _edit_correction_reward dedup (commits `979aee7`, `595a6de`)
- [x] T4: Maintenance analysis report (`.evomesh/shared/maintenance_analysis.md`)
