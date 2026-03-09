# Phase 26: Red Team Audit — Trainer-Perspective Gaming Analysis

Date: 2026-03-09

## Summary

9 attack surfaces analyzed from a white-box trainer perspective. 2 medium-high findings, 2 medium, 5 low.

## Findings

### Attack 1 — Question Distribution Predictability: LOW
- `_gq_retrieval_diverse()` deduplicates by entity+attribute
- Minor bias toward attribute-complete entities, but not exploitable
- No fix needed

### Attack 2 — Reasoning Answer Range Inference: MEDIUM
- **temporal_trend**: binary answer (rising/falling), 50% random baseline
- **temporal_extreme**: 5-choice, 20% baseline
- Other reasoning types: near 0% random baseline (exact numeric/name required)
- smart_guesser returns None for new dtype types → validated <5%
- **Recommendation**: Consider 5-level temporal_trend ("strongly rising/slightly rising/flat/slightly falling/strongly falling") to reduce baseline from 50% to 20%

### Attack 3 — Attribute Value Range Gaming: LOW
- smart_guesser validated <5% across all templates (10 seeds × 6 templates)
- Integer exact-match prevents guessing; float 2% tolerance too narrow to exploit
- No fix needed

### Attack 4 — Efficiency Axis Gaming: MEDIUM (post Phase 25)
- New formula `min(correct_total / write_budget, 1.0)` is write-count independent
- Not gameable: getting correct answers requires actual stored data
- Formula correctly incentivizes maximizing correctness, not minimizing writes
- No fix needed

### Attack 5 — Multi-Entity Packing: MEDIUM-HIGH
- `detect_stored_entities()` checks per-entry for name+value co-occurrence
- Agent CAN pack multiple entities per write: "Entity1: revenue 500, Entity2: employees 200"
- All packed entities would be correctly detected → scoring rewards packing
- With budget=30, packing 2-3 per write → effective 60-90 entity coverage
- **Design decision needed**: Is compression a valid memory management skill?
  - Argument FOR: smart compression IS what memory management is about
  - Argument AGAINST: bypasses budget pressure, the core design constraint
- **Recommendation**: Explicit design decision. If bug, add per-write entity count limit.

### Attack 6 — Correction Timing Predictability: MEDIUM
- Corrections at batch `int(n_batches * 0.6)`, contradictions at `int(n_batches * 0.8)`
- Fixed timing is predictable, but corrections are clearly labeled events
- Marginal gain from timing prediction (~5% maintenance improvement)
- **Recommendation**: Randomize correction position within [40%, 70%] range

### Attack 7 — Relationship Structure Inference: LOW
- Independent RNG (seed+9191), relationships visible in documents
- No hidden information to exploit
- No fix needed

### Attack 8 — Abstention Question Identification: LOW-MEDIUM
- Same `_q_text()` wording for real/fake entities
- trick_retrieval (2 questions) prevents always-abstain strategy
- Abstainer ceiling validated at 15%
- No fix needed

### Attack 9 — eval_salt Reversibility: LOW
- Salt is defense, not attack surface
- Ground truth uses salted values, so reversibility is irrelevant
- **Recommendation**: Enforce non-zero eval_salt in TIERS config for official evals

## Priority Matrix

| Finding | Threat | Actionable | Priority |
|---------|--------|------------|----------|
| Multi-entity packing | Medium-High | Design decision | High |
| temporal_trend baseline | Medium | Code change (5-level answer) | Medium |
| eval_salt default | Low | Config change | Low |
| Correction timing | Medium | Code change (randomize) | Low |

## Recommendations for Future Phases

1. **Phase 27 candidate**: Multi-entity packing — decide if feature or bug, implement accordingly
2. **Phase 27 candidate**: temporal_trend 5-level answer to reduce random baseline
3. **Config fix**: Add `eval_salt: 1` to TIERS in protocol.py
