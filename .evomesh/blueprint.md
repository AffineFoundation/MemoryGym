# memorybench-arena — Strategic Blueprint

> Lead-exclusive document, read-only for other roles. Review and update every 5 Loops.
> Last reviewed: Loop #35 (2026-03-22)

## Project Vision

Build a **realistic, cheat-proof, training-valuable** LLM memory management evaluation and training platform (MemoryGym). Goal: NeurIPS 2026 E&D Track paper submission (Abstract May 4, Paper May 6).

## Current Stage

**Phase 135 complete** (v0.10.37) — Evaluation system mature, maintenance analysis pipeline complete, training blocked on GPU.

### Established
- 10 domain templates (company/research/city/hospital/sport/movie/university/codebase/project/agentteam), each with 21-23 attributes
- 20 reasoning question types + 4-axis scoring (breadth 30% + maintenance 25% + reasoning 25% + efficiency 20%)
- 9 simulation strategies verifying scoring invariants
- 199 successful evaluations, covering 8 models
- RL training pipeline (GRPO) initially running, SFT verified ineffective (degradation ~9pp)
- Paper PA-26 complete, still needs radar chart, ablation, behavior example
- Maintenance axis: root cause analysis done, prompt fix deployed, diagnostics added, M formula investigated and confirmed
- Test coverage expanded: +22 unit tests (build_assistant_mask, common.py extraction, env.py dedup)
- Correction diagnostics in both bench.py (eval) and env.py (training)

### Key Metrics
- Strongest model Mistral-Small-24B: composite 24.3% (high variance)
- Maintenance axis: M=13.5%, 67% evals M=0 — **prompt fix deployed (T5a), awaiting validation**
- Base 3B C=29.5% >> Base 7B C=13.8% (smaller model outperforms)

## Technical Roadmap

### Short-term (by Mar 29)
1. **GRPO 30-step long training validation** — Confirm whether RL can stably improve memory management capabilities. ⛔ BLOCKED on GPU SSH since Mar 18.
2. **Post-fix evaluation batch** — Run evaluations with corrected prompt (T5a) to measure maintenance axis impact. Needs evaluator thread.
3. **Paper polishing** — PA-26 done; 3 items pending (radar chart, ablation, behavior example). Writer thread independent.

### Mid-term (Apr—May, pre-deadline)
4. **GiGPO exploration** — Two-layer credit assignment, highly relevant for multi-step memory tasks. Depends on GRPO results.
5. **More model evaluations** — Expand leaderboard coverage with new models on Chutes platform.
6. **R3/R4 data-gated decisions** — Case-insensitive Edit matching + M formula change. Pending real eval correction diagnostics.

### Long-term (post-submission)
7. **Multi-agent memory collaboration** — Extend from single agent to multi-agent scenarios
8. **Training effect transfer validation** — Verify trained models improve in real agent scenarios
9. **Training curriculum** — Adaptive difficulty based on 4-axis scores

## Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Scoring method | 4-axis independent | Avoid single metric masking capability gaps |
| Correction Edit free | Yes (Phase 112) | Should not penalize correct behavior due to budget |
| SFT route | Abandoned | 7B/3B both degraded, RL more promising |
| Small model priority | 3B > 7B | Data-driven, 3B baseline is stronger |
| Training framework | verl + slime | Multi-framework risk hedging |
| M formula | Keep current with coverage gate (D2) | Alt formula equivalent in simulation; revisit with real data |
| Correction demo in prompt | Rejected (D1) | Violates prompt neutrality — correction workflow is capability under test |

## Risk Items

| Risk | Impact | Status | Mitigation |
|------|--------|--------|------------|
| GPU access blocked (since Mar 18) | Training completely stalled — 4+ days | 🔴 CRITICAL | Escalate to infra; all local prep exhausted; consider cloud GPU fallback |
| NeurIPS deadline tight (43 days) | Abstract May 4, Paper May 6 | 🟡→🟠 | Paper thread polishing; parallelize non-GPU work; GPU block threatens training results |
| GRPO doesn't converge | Paper lacks training results | 🟡 | GiGPO as backup; reward shaping tuned |
| Maintenance axis validation | Fix deployed but unvalidated | 🟡 NEW | Run post-fix eval batch with correction diagnostics |
| stream_agent.py approaching 1000 lines | 876 lines, nearing split threshold | ⚪ MONITOR | Split if it crosses 900 |
