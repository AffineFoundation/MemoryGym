# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #9

## Overall Status: 🟡 Idle — awaiting GPU + eval data

Version: v0.10.37 | Phase 135 complete | Tests: 444+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟡 Idle | T5 complete, awaiting assignment | T1-T5 all done |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 evaluations; next batch should use updated prompt |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 |
| WRITER | ⚪ Never created | — | Paper thread via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | — |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟡 Loop #9 (idle 1/3) | Self-audit, monitoring |
| executor | 🔵 Light mode | T1-T5 complete, awaiting dispatch |
| trainer | 🔴 Light mode | GPU blocked since Mar 18 (16 loops) |

## Loop #9 Actions

1. **Self-audit** — no tasks, no inbox. All roles reviewed.
2. **Trainer commit noted**: `b201f7b` — correction diagnostics added to env.py (proactive, mirrors T5b)
3. **All roles idle or blocked**. Project in legitimate pause. Critical path: GPU + eval data.

## Maintenance Axis Status

Pipeline complete:
- T4: Root cause analysis (5 causes identified)
- D1: Decisions on recommendations (R1+R5 approved, R2 rejected, R3/R4 deferred)
- T5a: Prompt contradiction fixed (commit `259a936`)
- T5b: Correction diagnostics added to bench.py
- T5c: M formula comparison done — keep current
- **Next**: Run evaluations with corrected prompt to measure impact on M scores

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% M=0 — prompt fix deployed, awaiting validation
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: PA-26 complete, 3 items pending (radar, ablation, behavior example)

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked (2+ days) | Trainer / infra |
| No post-fix eval data | Can't validate maintenance improvement | Evaluator thread |
