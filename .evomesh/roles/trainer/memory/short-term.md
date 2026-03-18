# Short-term Memory

## Done (Loop 1, 2026-03-18)
- Read full TRAINER.md (2060 lines), 56+ frontier research findings (F1-F56)
- Wired up `--rollout-max-tokens` and `--turn-level` CLI args to GRPO training
- Turn-level advantage: 50/50 mix of episode outcome + cumulative shaped reward
- `rollout_max_tokens` now configurable (was hardcoded 16384)
- Per-turn shaped reward collection (`turn_rewards` in stats)
- Committed and pushed: `334f83c`

## Blockers
- **GPU SSH blocked**: Cannot connect (permission denied). Code is pushed, experiment ready to execute but needs SSH access
- **No pytest locally**: Cannot run test suite (pip install blocked by permissions)

## In-progress
- GRPO v4a experiment command is ready, waiting for GPU access

## Next Focus
1. When GPU available: run GRPO v4a 3-step experiment
2. If GPU stays blocked: explore Training-Free GRPO (F28) — context space optimization using Chutes API, no GPU needed
3. Strategic: analyze whether F28 is feasible given current SFT trajectory data
