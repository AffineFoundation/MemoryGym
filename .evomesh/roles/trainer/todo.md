# trainer — Tasks

## P0 — GRPO v4a Experiment

1. ~~Read sessions/TRAINER.md for full context~~ ✅
2. ~~Wire up --rollout-max-tokens and --turn-level CLI args~~ ✅
3. ~~Fix KL divergence to Schulman k3~~ ✅
4. ~~Implement true turn-level GRPO (per-token advantages)~~ ✅
5. Commit + push
6. SSH to GPU, run GRPO v4a 3-step experiment
7. Record results to devlog/, analyze effective gradient rate

## P1 — Code Quality (GPU-blocked idle work)

- Audit env.py reward edge cases
- Review SFT data quality (data/sft_v6*.jsonl)
- Training data analysis: what turn_rewards distributions look like
