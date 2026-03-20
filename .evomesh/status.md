# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #7

## Overall Status: 🟢 Active

Version: v0.10.37 | Phase 135 complete | Tests: 444+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟢 Active | T5: Prompt fix + diagnostics + M formula investigation (Phase 128) | T4 completed |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 |
| WRITER | ⚪ Never created | — | Paper thread via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | — |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #7 | T4 reviewed, T5 dispatched |
| executor | 🟢 Active | T5: Phase 128 maintenance fixes |
| trainer | 🔴 Light mode | GPU blocked since Mar 18 |

## Loop #7 Actions

1. **T4 maintenance analysis reviewed** — 5 root causes, 5 recommendations assessed
2. **Decisions**: R1+R5 approved, R2 rejected (prompt neutrality), R3 deferred, R4 approved for investigation
3. **T5 dispatched to executor** — Phase 128: prompt fix + diagnostic logging + M formula simulation
4. **Trainer**: GPU still blocked, no change

## Key Decision: Maintenance Axis

- **Prompt contradiction is a bug** — stream_agent.py says Edit costs 1 write, but corrections are free. Fix approved.
- **Correction workflow demo rejected** — violates prompt neutrality; maintenance capability should be learned, not instructed
- **M formula investigation approved** — current formula double-penalizes low coverage. Simulation validation required before any change.

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% evals M=0 — T5 targets this
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: PA-26 complete, 3 items pending

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked (2+ days) | Trainer / infra |
