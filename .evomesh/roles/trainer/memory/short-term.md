# Short-term Memory

## Done (Loop 5, 2026-03-18)
- SFT data quality review: 320 trajectories, well-structured (avg 970 chars/Write, 6 entities/Write, 100% search-before-edit)
- Data quality not the bottleneck — SFT signal too weak for 7B/3B, confirms RL is correct path
- Self-evolution audit: updated ROLE.md with current status + 4 project-specific rules learned from loops 1-4

## Done (Loops 1-4)
- CLI args, KL k3 fix, turn-level GRPO, env.py edge case fixes — all committed+pushed

## Blockers
- **GPU SSH blocked**: permission denied — all code prep done, experiment ready
- **No pytest locally**: pip install blocked

## Status
- 5 loops complete, 4 code commits pushed
- Next meaningful work requires GPU access
- Approaching idle threshold (3× idle → light mode per CLAUDE.md)
