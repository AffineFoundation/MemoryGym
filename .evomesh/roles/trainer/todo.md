# trainer — Tasks

## P0 — GRPO v4a Experiment

1. ~~Read sessions/TRAINER.md for full context~~ ✅
2. ~~Wire up --rollout-max-tokens and --turn-level CLI args~~ ✅
3. ~~Fix KL divergence to Schulman k3~~ ✅
4. Commit + push KL fix
5. SSH to GPU, run GRPO v4a 3-step experiment
6. Record results to devlog/, analyze effective gradient rate

## P1 — Root Cause Analysis (updated)

- 30% effective rate caused by: (a) similar rewards → advantage ≈ 0, (b) wrong KL allowing policy drift
- v4a fixes: context pressure + turn-level advantage + correct KL
- KL fix ensures policy stays near reference → prevents reward collapse → more diverse rollouts
