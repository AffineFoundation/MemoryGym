# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-22 Loop #35

## Overall Status: 🟡 Idle — awaiting GPU + eval data

Version: v0.10.37 | Phase 135 complete | Tests: 461+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🔵 Light mode | T1-T5 complete | Awaiting dispatch |
| EVALUATOR | 🟢 Running | Continuous evaluation | Next batch must use updated prompt (T5a) |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH blocked since Mar 18 (4+ days) |
| WRITER | ⚪ Never created | — | Paper thread via sessions/WRITER.md |
| AUDITOR | 🟢 Running | Continuous auditing | — |

## evomesh Role Status

| Role | Status | Loop | Current Task |
|------|--------|------|--------------|
| lead | 🟢 Active | #35 | Blueprint review (5-loop cycle) |
| executor | 🔵 Light mode | #24 | Awaiting dispatch |
| trainer | 🔴 Light mode | #32 | GPU blocked since Mar 18 |

## Loop #35 Actions

1. **Blueprint review** — Updated risk severity: NeurIPS deadline upgraded 🟡→🟠 (43 days to abstract, GPU block threatens training results). Added cloud GPU fallback to mitigations.
2. **No direction change warranted** — Project remains infrastructure-blocked, not strategy-blocked. All code prep exhausted across all roles.
3. **File size check**: stream_agent.py stable at 876 lines (under 1000 limit).
4. **Role health**: All roles healthy but idle. Executor (Loop #24), Trainer (Loop #32) — both in light mode, no anomalies.

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

| Blocker | Impact | Owner | Duration |
|---------|--------|-------|----------|
| GPU SSH permission denied | Training completely blocked | Trainer / infra — CRITICAL | 4+ days (since Mar 18) |
| No post-fix eval data | Can't validate maintenance improvement | Evaluator thread | Pending |
