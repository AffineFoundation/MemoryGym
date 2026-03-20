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

## Done (Loop 14, 2026-03-20)
- Fixed RC1 system prompt contradiction in stream_agent.py (Edit "costs 1 write" → "free during correction events")
  - Executor's T4 analysis identified this as HIGH impact root cause for M=0 in 67% of evals
  - eval_task.py already had the fix; stream_agent.py (used by bench.py + training env) did not
  - Now both prompts consistently communicate that Edits are free during corrections

## Done (Loop 15, 2026-03-20)
- Added correction diagnostics to env.py episode_stats (mirrors executor's T5b bench.py diagnostics)
  - Tracks per-episode: total corrections, with_search, with_edit, edit_success
  - Critical for debugging GRPO v4a maintenance reward signal when GPU available
- Reviewed executor's T5b/T5c changes — env.py reward logic confirmed sound, M formula change pending lead decision

## Done (Loop 20, 2026-03-20)
- Fixed parallel bug: ported per-token turn-level advantage from cli.py to scripts/grpo_train.py
  - grpo_train.py had old episode-level mixing (scalar advantage for all tokens)
  - Now uses build_turn_advantage_weights() for per-token advantage from turn rewards
  - Both scripts now share identical turn-level GRPO logic
  - This is the critical v4a feature — high-reward Write turns get amplified gradients

## Status
- 20 loops, GPU still blocked
- Next action: commit turn-level fix, then light mode until GPU access or new inbox
