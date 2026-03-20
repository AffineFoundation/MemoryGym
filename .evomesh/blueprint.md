# memorybench-arena — Strategic Blueprint

> Lead-exclusive document, read-only for other roles. Review and update every 5 Loops.

## Project Vision

Build a **realistic, cheat-proof, training-valuable** LLM memory management evaluation and training platform (MemoryGym). Goal: NeurIPS 2026 E&D Track paper submission (Abstract May 4, Paper May 6).

## Current Stage

**Phase 135 complete** (v0.10.37) — Evaluation system mature, training module initially usable.

### Established
- 10 domain templates (company/research/city/hospital/sport/movie/university/codebase/project/agentteam), each with 21-23 attributes
- 20 reasoning question types + 4-axis scoring (breadth 30% + maintenance 25% + reasoning 25% + efficiency 20%)
- 9 simulation strategies verifying scoring invariants
- 199 successful evaluations, covering 8 models
- RL training pipeline (GRPO) initially running, SFT verified ineffective (degradation ~9pp)
- Paper PA-26 complete, still needs radar chart, ablation, behavior example
- `build_assistant_mask` fully unit-tested (5 tests, mock tokenizer)

### Key Metrics
- Strongest model Mistral-Small-24B: composite 24.3% (high variance)
- Maintenance axis is an independent bottleneck: M=13.5%, 67% evals M=0
- Base 3B C=29.5% >> Base 7B C=13.8% (smaller model outperforms)

## Technical Roadmap

### Short-term (within 2 weeks)
1. **GRPO 30-step long training validation** — Confirm whether RL can stably improve memory management capabilities
2. **Continued paper quality polishing** — After PA-23, 3 items still pending (radar, ablation, behavior example)
3. **Maintenance axis improvement** — Models not executing correction Edit is the main cause

### Mid-term (1-2 months)
4. **GiGPO exploration** — Two-layer credit assignment, highly relevant for multi-step memory tasks
5. **More model evaluations** — Expand leaderboard coverage
6. **Training curriculum** — Adaptive difficulty based on 4-axis scores

### Long-term
7. **Multi-agent memory collaboration** — Extend from single agent to multi-agent scenarios
8. **Training effect transfer validation** — Verify capability improvement of trained models in real agent scenarios

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Scoring method | 4-axis independent | Avoid single metric masking capability gaps |
| Correction Edit free | Yes (Phase 112) | Should not penalize correct behavior due to budget |
| SFT route | Abandoned | 7B/3B both degraded, RL more promising |
| Small model priority | 3B > 7B | Data-driven, 3B baseline is stronger |
| Training framework | verl + slime | Multi-framework risk hedging |

## Risk Items

| Risk | Impact | Mitigation |
|------|--------|------------|
| GRPO long training doesn't converge | Paper lacks training data | GiGPO as backup; tune reward shaping |
| GPU access blocked since Mar 18 | Training completely stalled, 0 progress for 2+ days | Escalate to infra; all local prep exhausted |
| NeurIPS deadline is tight (45 days) | Abstract May 4, Paper May 6 | Paper thread continues polishing; parallelize non-GPU work |
| Maintenance axis too low (67% M=0) | Weak evaluation discriminability | Analyze model behavior — assigned to executor as T3 |
