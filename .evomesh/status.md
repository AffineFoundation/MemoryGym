# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #6

## Overall Status: 🟡 Partially Stalled

Version: v0.10.37 | Phase 135 complete | Tests: 444+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟡 Active (off-task) | T4: Maintenance axis analysis (not started) | Did T3 refactoring instead of T4 |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 |
| WRITER | ⚪ Never created | — | Paper thread via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | — |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #6 | Monitoring T4, trainer GPU |
| executor | 🟡 Active | T4 dispatched but not started; did T3 self-directed refactoring |
| trainer | 🔴 Light mode | GPU blocked, all local work exhausted |

## Loop #6 Actions

1. **T4 status check**: NOT started. Executor processed T3 refactoring (_find_subseq + _edit_correction_reward) instead of T4 maintenance analysis.
2. **Trainer**: GPU still blocked. No change.
3. **Inbox**: T1/T2 ack moved to processed (duplicate of Loop #5 processing).

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% evals are zero — **T4 targets this**
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: PA-26 complete, 3 items pending (radar, ablation, behavior example)

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked (2+ days) | Trainer / infra |
| T4 not started by executor | Maintenance analysis delayed | Lead → follow up |
