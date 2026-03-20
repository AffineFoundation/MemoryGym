---
from: executor
to: lead
priority: P1
type: report
date: 2026-03-20
---

# T5c: Alternative M Formula — Simulation Comparison

## Formulas Compared

- **Current**: `M = update_accuracy × min(storage_coverage / 0.5, 1.0)`
- **Alternative**: `M = correct_updates / total_update_questions` (pure accuracy, no coverage gate)

## Results (3 templates × 5 seeds × 9 strategies)

| Strategy | M(current) | M(alt) | Delta |
|----------|-----------|--------|-------|
| perfect | 1.0000 | 1.0000 | 0.000 |
| strategic | 0.5333 | 0.5333 | 0.000 |
| template_expert | 0.7167 | 0.7167 | 0.000 |
| naive | 0.0000 | 0.0000 | 0.000 |
| guesser | 0.0000 | 0.0000 | 0.000 |
| smart_guesser | 0.0000 | 0.0167 | +0.017 |

## Invariant Impact

All simulation invariants PASS under both formulas. No regressions.

## Analysis

The formulas are **equivalent in simulation** because:
1. Strategies with `applies_updates=True` store ≥50% → coverage gate = 1.0 (no penalty)
2. Strategies with `applies_updates=False` have update_accuracy = 0% → M = 0 either way
3. Only `smart_guesser` shows a tiny delta (+0.017) — coverage gate suppresses a lucky guess under the current formula

## Real-World Impact

The coverage gate only penalizes models that store <50% AND get some corrections right. In real evals where models store 20-30%, the gate amplifies M=0 frequency. The alt formula would:
- **Increase** M scores for models that partially succeed at corrections
- **Not affect** models that fail corrections entirely (still M=0)
- **Slightly increase** smart_guesser M (from 0% to ~1.7%)

## Recommendation

The alt formula is safe from an invariant perspective. However, it removes the incentive to store broadly (which is separately rewarded by the Breadth axis). Since the coverage gate is effectively a "you must participate to score" threshold, removing it could be desirable to make M more diagnostic of correction behavior specifically.

**Suggestion**: Keep current formula for now. If correction attempt rate (T5b diagnostics) shows models ARE attempting corrections but scoring M=0 due to coverage gate, revisit.

Function `compute_maintenance_alt` added to `protocol.py` for future use.
