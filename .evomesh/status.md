# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #5

## Overall Status: 🟡 Partially Stalled (improving)

Version: v0.10.37 | Phase 135 complete | Tests: 444+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟢 Active | T3: Maintenance axis analysis | T1/T2 done, T3 assigned |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 (12 loops in light mode) |
| WRITER | ⚪ Never created | — | Backlog — paper thread runs via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | A536 complete |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #5 | Blueprint review + T3 assignment |
| executor | 🟢 Active | T3: maintenance axis investigation (no GPU needed) |
| trainer | 🔴 Light mode | GPU blocked, all local work exhausted (12 loops) |

## Loop #5 Actions

1. **Executor T1/T2 confirmed complete** — 5 unit tests for `build_assistant_mask` merged (commit `ee817d0`). Test code reviewed, quality approved.
2. **Blueprint reviewed** — Updated paper status PA-26, added GPU risk, refined maintenance risk.
3. **T3 assigned to executor** — Maintenance axis analysis: why 67% M=0? Code + behavior investigation, no GPU needed.
4. **Trainer**: GPU SSH still blocked, 12 loops light mode. No action possible.

## Uncommitted Changes

Modified files from other roles (not lead's):
- `memorygym/training/common.py`: local modifications (may conflict with committed version)
- Various role state files (heartbeat, metrics, short-term memory)

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% evals are zero — **T3 targets this**
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: PA-26 complete, 3 items pending (radar, ablation, behavior example)

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked (2+ days) | Trainer / infra — escalate? |
