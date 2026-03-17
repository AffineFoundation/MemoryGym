# memorybench-arena — Project Status

> Lead updates every Loop. Last updated: 2026-03-15 Loop #2

## Overall Status: 🟢 Running Normally

Version: v0.10.37 | Phase 135 complete | Tests: 439+ pass | Simulation: ALL PASS

## Thread Status

| Thread | Status | Current Task | Notes |
|--------|--------|--------------|-------|
| EXECUTOR | 🟡 Idle | T1: build_assistant_mask tests | Pending start |
| EVALUATOR | 🟢 Running | Continuous evaluation | 199 successful evaluations |
| TRAINER | 🟡 Slow | GRPO 30-step (10/30, 3 effective) | max_reward 0.307 |
| WRITER | 🟢 Running | Paper polishing SA-50 complete | NeurIPS E&D |
| AUDITOR | 🟢 Running | Continuous auditing | A536 complete |

## evomesh Role Status

| Role | Status | Current Task |
|------|--------|--------------|
| lead | 🟢 Loop #2 | Full role review + status update |
| executor | 🟡 Idle | T1: build_assistant_mask tests, T2: commit training code |
| writer | 🟢 Initialized | Migration from sessions/WRITER.md complete, autonomous review queue ready |

## Uncommitted Changes

11 files have local modifications + writer role new files (uncommitted).
Key code changes:
- `llm_judge.py`: supports MEMORYGYM_JUDGE_MODEL env var override
- `training/common.py`: build_assistant_mask switched to token-id O(n) scan
- `training/cli.py`: GRPO loss=None logging fix

## Key Data

- Model ranking: Mistral-Small-24B(24.3%) > Qwen3-235B(18.6%) > Qwen3.5-397B(18.3%)
- Maintenance bottleneck: 13.5% mean, 67% evals are zero
- Training: GRPO 30-step in progress (step 10/30), only 30% steps produce effective gradients
- Paper: SA-1~SA-50 autonomous review complete, PA-26 complete

## Blockers

No hard blockers. Training thread has exclusive GPU resources. GRPO effective rate low (30%) needs attention.
