# trainer — Tasks

## P0 — GRPO v4a Experiment

1. ~~Read sessions/TRAINER.md for full context~~ ✅
2. ~~Wire up --rollout-max-tokens and --turn-level CLI args~~ ✅
3. Commit + push code changes
4. SSH to GPU, run GRPO v4a 3-step experiment:
   `--tier standard --rollout-max-tokens 6144 --ips --kl-coeff 0.05 --turn-level --steps 3 --group-size 2 --groups-per-step 1`
5. Record results to devlog/, analyze effective gradient rate

## P1 — Root Cause Analysis

- GRPO 30-step had only 30% effective gradient steps (3/10 had loss != 0)
- Root cause: group_size=4 with standard tier still produces too-similar rewards → advantage ≈ 0
- v4a addresses this with: context pressure (rollout-max-tokens=6144) + turn-level advantage (shaped rewards create differentiation)
- If v4a still has low effective rate → increase group_size or try IPS more aggressively
