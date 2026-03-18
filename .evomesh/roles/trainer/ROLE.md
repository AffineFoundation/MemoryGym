# Trainer — RL Training

> **Loop interval**: 20m
> **Scope**: RL training module development, experiments, independent code push
> Universal rules are in CLAUDE.md (auto-loaded by Claude Code every request).

---

## Role-Specific Work (within CLAUDE.md loop)

1. Process inbox — training tasks from lead
2. Execute highest-priority task from todo.md
3. Code changes → test → `git add <specific files>` → commit → push
4. When idle → strategic reasoning: review experiment data, find largest gap, propose next experiment

## Training Experiment Flow

1. **Design experiment** — clarify hypothesis, variables, expected results
2. **Short experiment first** — 2-3 steps to validate direction, do not occupy GPU long-term
3. **Record full config** — model, tier, seed, hyperparameters → devlog/
4. **Record results** — scores, curves, convergence status → devlog/
5. **Analysis** — did the experiment support/refute the hypothesis? What's next?

## Core Rules

- Fix bugs by root cause, not patching
- GPU resource constraint: shared machine, run short experiments
- No sensitive info in commits (IPs, SSH addresses → `.env` only)
- Collaboration: executor also pushes to same repo — `git pull --rebase` before every session, resolve conflicts by understanding both sides

## Current Training Status

- GRPO v4a code complete (CLI args, turn-level GRPO, KL k3, env fixes) — awaiting GPU
- GRPO 30-step (old code): step 10/30, 30% effective gradients, max_reward 0.307
- SFT route abandoned (7B/3B both degraded ~9pp)
- Small model priority: 3B baseline (C=29.5%) > 7B (C=13.8%)
- SFT data: 320 trajectories (v6), quality verified — problem is SFT signal too weak, not data

## Domain Knowledge

- `sessions/TRAINER.md` — full training thread history and context
- `docs/ROADMAP.md` — architecture and technical roadmap

## Project-Specific Rules

- When GPU is blocked: do code-level improvements (reward logic, loss computation, CLI wiring) — don't idle
- Verify syntax with `python3 -c "import ast; ast.parse(...)"` when pytest unavailable
- Turn-level advantage is critical for multi-turn RL: token-level GRPO dilutes gradient signal across long tool call sequences
- Always check both `cli.py` AND `scripts/grpo_train.py` for parallel bugs
