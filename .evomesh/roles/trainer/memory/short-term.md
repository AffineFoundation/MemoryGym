# Short-term Memory

## Done (Loop 3, 2026-03-18)
- Implemented true turn-level GRPO (MT-GRPO/F48 inspired):
  - `build_turn_advantage_weights()` in common.py: maps per-turn advantages to token spans
  - Per-turn advantage = episode_advantage * (1 + normalized_turn_reward)
  - High-reward turns (Write with entity match → +0.5) get amplified gradients
  - Low-reward turns (wasted actions) get dampened gradients
  - Falls back to scalar advantage where no turn mapping exists
- Fixed `_save_episode_samples` to handle new 3-tuple trajectory format

## Done (Loop 2)
- Fixed KL divergence → Schulman k3 (commit `4f25263`)

## Done (Loop 1)
- Wired up `--rollout-max-tokens` and `--turn-level` CLI args (commit `334f83c`)

## Blockers
- **GPU SSH blocked**: Cannot connect (permission denied)
- **No pytest locally**: pip install blocked

## Next Focus
1. Commit turn-level GRPO + push
2. When GPU available: v4a experiment with full turn-level
3. Idle: audit env.py reward edge cases, or explore training data quality
