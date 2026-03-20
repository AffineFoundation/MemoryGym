# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #7

## Overall Status: 🟢 Active

Version: v0.10.37 | Phase 135 complete | Tests: 444+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟢 Active | T5: Implement R1+R5 (prompt fix + diagnostic logging) | T4 completed, T5 assigned |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 |
| WRITER | ⚪ Never created | — | Paper thread via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | — |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #7 | T4 reviewed, decisions recorded, T5 dispatched |
| executor | 🟢 Active | T5: R1 (prompt fix) + R5 (diagnostic logging) |
| trainer | 🔴 Light mode | GPU blocked, all local work exhausted |

## Loop #7 Actions

1. **T4 maintenance analysis reviewed** — 5 root causes, 5 recommendations assessed against design principles
2. **Decisions recorded** in `shared/decisions.md` D1: R1+R5 approved, R2 rejected (prompt neutrality), R3+R4 deferred
3. **T5 dispatched to executor** — Implement R1 (fix Edit cost description in system prompt) + R5 (correction diagnostic logging)
4. **Trainer**: GPU still blocked. No change.

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% evals are zero — R1 prompt fix expected to help
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: PA-26 complete, 3 items pending (radar, ablation, behavior example)

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked (2+ days) | Trainer / infra |
