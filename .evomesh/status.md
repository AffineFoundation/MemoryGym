# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #4

## Overall Status: 🟡 Partially Stalled

Version: v0.10.37 | Phase 135 complete | Tests: 439+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟡 Idle | T1: build_assistant_mask tests | P1 sent, awaiting processing (1 loop grace) |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH permission denied since Mar 18 |
| WRITER | ⚪ Never created | — | Confirmed: zero git history, was never initialized |
| AUDITOR | 🟢 Running | Continuous auditing | A536 complete |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #4 | Status update, P1 follow-up |
| executor | 🟡 Light mode | P1 inbox pending — T1/T2 don't need GPU |
| trainer | 🔴 Light mode | GPU blocked, all local work exhausted (11 loops) |

## Issues Identified (Loop #4)

1. **Writer role confirmed never created** — git log shows zero history. Moved to backlog (paper thread operates independently via sessions/WRITER.md).
2. **Executor P1 not yet processed** — Inbox placed at ~09:02, executor heartbeat at 08:50 (before placement). Giving 1 more loop grace. If unprocessed by Loop #5, escalate.
3. **Trainer GPU blocker persists** — 11 loops complete, all in light mode. Nothing actionable by lead.
4. **Git pull resolved** — `git pull --rebase` working normally again.

## Uncommitted Changes

Modified files from other roles (not lead's):
- `training/common.py`: build_assistant_mask token-id O(n) refactor
- `training/cli.py`: GRPO loss=None logging fix
- `llm_judge.py`: MEMORYGYM_JUDGE_MODEL env var override
- Various role state files (heartbeat, metrics, short-term memory)

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% evals are zero
- Training: GRPO blocked on GPU — no progress since step 10/30
- Paper: SA-1~SA-50 autonomous review complete, PA-26 complete

## Blockers

| Blocker | Impact | Owner |
|---------|--------|-------|
| GPU SSH permission denied | Training completely blocked | Trainer / infra |
| Writer evomesh role missing | Low impact — paper thread runs independently | Backlog |
