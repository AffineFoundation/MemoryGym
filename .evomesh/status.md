# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #10

## Overall Status: 🟡 Idle — awaiting GPU + eval data

Version: v0.10.37 | Phase 135 complete | Tests: 461+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🔵 Light mode | T1-T5 complete | Awaiting dispatch |
| EVALUATOR | 🟢 Running | Continuous evaluation | Next batch must use updated prompt (T5a) |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 |
| WRITER | ⚪ Never created | — | Paper thread via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | — |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #10 | Blueprint review (5-loop cycle) |
| executor | 🔵 Light mode | Awaiting dispatch |
| trainer | 🔴 Light mode | GPU blocked since Mar 18 |

## Loop #10 Actions

1. **Blueprint review completed** — updated roadmap, risk table, architecture decisions. Reflects maintenance pipeline completion (T4→D1→T5→D2), test coverage gains (+22 tests), and updated risk severity.
2. **Key strategic finding**: No direction change warranted. Project in legitimate pause. Bottleneck is infrastructure (GPU), not strategy or code.
3. **File size check**: All core files under 1000 lines. stream_agent.py at 876 — added to monitoring.

## Maintenance Axis Status

Pipeline complete:
- T4: Root cause analysis (5 causes identified)
- D1: Decisions (R1+R5 approved, R2 rejected, R3/R4 deferred)
- T5a: Prompt contradiction fixed (commit `259a936`)
- T5b: Correction diagnostics in bench.py + env.py
- T5c + D2: M formula confirmed, data-gated revisit
- **Next**: Post-fix evaluation batch

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance: 67% M=0 — prompt fix deployed, awaiting validation
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: PA-26, 3 items pending (radar, ablation, behavior example)

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked (2+ days) | Trainer / infra — CRITICAL |
| No post-fix eval data | Can't validate maintenance improvement | Evaluator thread |
