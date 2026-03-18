# Short-term Memory

## Done (Loop 4, 2026-03-18)
- Audited env.py reward edge cases, found and fixed 3 issues:
  1. **AttributeError bug**: `_make_obs()` doesn't exist, called when submit_answer with no event → fixed to "Episode complete."
  2. **Event skipping via submit_answer**: calling submit_answer during non-question events would advance event_idx, allowing reward hacking → now only advances for questions, penalizes (-0.05) otherwise
  3. **No penalty for oversized Write**: content > 2000 chars got no reward signal → added -0.05 penalty

## Done (Loops 1-3)
- CLI args `--rollout-max-tokens` + `--turn-level` (Loop 1)
- KL → Schulman k3 (Loop 2)
- True turn-level GRPO with per-token advantages (Loop 3)

## Blockers
- **GPU SSH blocked**: permission denied
- **No pytest locally**: pip install blocked

## Next Focus
1. Commit env.py fixes + push
2. When GPU available: GRPO v4a experiment
3. Idle: self-evolution audit of ROLE.md, or SFT data quality review
