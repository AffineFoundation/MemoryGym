# Short-term Memory

## Done (Loop 6, 2026-03-18)
- F28 (Training-Free GRPO) feasibility assessment:
  - ~28K tokens per trajectory, few-shot would push context to 130K+
  - ~$10 for 40-eval optimization run — cost is reasonable
  - **Verdict: not suitable for paper** — optimizes prompt not weights, paper needs model training results
  - Useful as prompt engineering tool, but not a GPU substitute for NeurIPS claims
- All P1 idle work exhausted

## Done (Loops 1-5)
- CLI args, KL k3 fix, turn-level GRPO, env.py fixes, SFT data review, ROLE.md audit

## Blockers
- **GPU SSH blocked**: permission denied — all code prep done

## Status
- 6 loops complete, no remaining local work
- **Entering light mode** (3× idle threshold reached: loops 5, 6 are idle)
- Light mode: inbox + memory/metrics only, no git commit/push
