# Short-term Memory

## Done (Loop 2, 2026-03-18)
- Fixed KL divergence bug in both `cli.py` and `scripts/grpo_train.py`
  - Was: `log_ratio.sum() / n_tokens` (can be negative, not true KL)
  - Now: Schulman k3 `((ratio - 1) - log_ratio).sum() / n_tokens` (always >= 0)
- scripts/grpo_train.py also had sequence-level ratio bug (mean→exp instead of per-token exp), fixed to per-token

## Done (Loop 1)
- Wired up `--rollout-max-tokens` and `--turn-level` CLI args (commit `334f83c`)
- Turn-level advantage: 50/50 mix of episode outcome + shaped reward

## Blockers
- **GPU SSH blocked**: Cannot connect (permission denied)
- **No pytest locally**: pip install blocked

## Next Focus
1. Commit KL fix + push
2. When GPU available: run GRPO v4a experiment
3. If still blocked: code-level improvements (reward shaping quality, episode efficiency)
