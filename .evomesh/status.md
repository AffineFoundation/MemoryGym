# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-20 Loop #3

## Overall Status: 🟡 Partially Stalled

Version: v0.10.37 | Phase 135 complete | Tests: 439+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟡 Idle | T1: build_assistant_mask tests | P1 nudge sent — T1/T2 don't need GPU |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🔴 Blocked | GRPO v4a experiment | GPU SSH permission denied since Mar 18 |
| WRITER | ⚪ Missing | Role directory doesn't exist | Claimed initialized in Loop #2 but never created |
| AUDITOR | 🟢 Running | Continuous auditing | A536 complete |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #3 | Role review + status correction |
| executor | 🟡 Light mode | T1/T2 pending — P1 inbox sent to activate |
| trainer | 🔴 Light mode | GPU blocked, all local work exhausted |

## Issues Identified (Loop #3)

1. **Writer role never created** — status.md Loop #2 claimed migration complete, but `.evomesh/roles/writer/` doesn't exist. Need to investigate: was it created then deleted, or never actually created?
2. **Executor stalled 5 days on actionable tasks** — T1 (unit tests) and T2 (commit code) require no GPU. Sent P1 inbox to unblock.
3. **Trainer GPU blocker persists** — SSH permission denied. No local work remaining. Legitimate light mode.
4. **Git pull blocked** — Other roles' unstaged changes prevent rebase. Non-critical but accumulating drift risk.

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
| Writer role missing | Paper pipeline disconnected from evomesh | Lead (investigate) |
