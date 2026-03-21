# MemoryGym System Critique: Evaluation & Training Perspectives

> Date: 2026-03-21
> Author: data-memory role (affine-swarm)
> Context: After 40+ loops of building SFT data, attempting GPT-5.4 distillation, and iterating through 6 versions of hybrid generators, these are the accumulated insights about MemoryGym's design.

---

## Part 1: As an Evaluation System

### What MemoryGym Gets Right

**1. Asks the Right Question**

Among all memory benchmarks (LoCoMo, LongMemEval, MemoryAgentBench, AMA-Bench, AMemGym, MemoryBench), MemoryGym is the only one that asks: **"Under a limited budget, what should you remember?"**

Every other benchmark assumes unlimited storage. But real-world agents face constraints: context windows are finite, vector stores cost money, retrieval has noise. The budget constraint (30 entities, 15 writes) forces genuine prioritization — this is a valuable and unique contribution.

**2. Serious Anti-Cheating**

9 simulation strategies systematically verify that scores reflect real capability:

| Strategy | Store | Updates | Expected Score | What It Catches |
|----------|-------|---------|---------------|-----------------|
| perfect | 100% | Yes | 100% | Baseline ceiling |
| guesser | 0% | No | 0% | Catches random guessing |
| smart_guesser | 0% | No | ≤5% | Catches pattern exploitation |
| abstainer | 100% | Yes | <15% | Catches "always abstain" |
| strategic | 70% | Yes | >naive+10% | Validates strategy matters |
| naive | 40% | No | Baseline floor | Shows update value |

Most benchmarks don't have this level of validation. The simulation suite is genuinely well-designed.

**3. Deterministic Reproducibility**

Same seed = identical scenario (entities, documents, corrections, questions). Essential for scientific comparison and leaderboard fairness. World generation, correction placement, and question selection are all seeded.

**4. Multi-Axis Diagnostics**

Rather than a single score, MemoryGym decomposes into 4 interpretable axes:
- **Storage Breadth (30%)**: Did you store this entity?
- **Memory Maintenance (25%)**: Did you update the corrected value?
- **Reasoning (25%)**: Can you compute from stored data? (20 question types)
- **Efficiency (20%)**: Correct answers per budget unit

This lets you diagnose *where* a model fails, not just *that* it fails.

**5. Rich Domain Diversity**

10 world templates (company, research, city, hospital, sport, movie, university, codebase, project, agentteam) with typed attributes (6 dtypes), relationships, corrections, contradictions, and 20+ reasoning question types. This prevents overfitting to a single domain.

### Evaluation Score: 7/10

---

## Part 2: Design Problems (Evaluation Perspective)

### Problem 1: Context Redaction Is Too Aggressive

After every event, the entire conversation is wiped:
```
[system prompt]
[user: "Your memory contains 15 entries: A, B, C..." ]
[assistant: "OK."]
[user: next event]
```

The model loses ALL context about what it stored, what corrections it applied, and what documents it saw. It only knows entity names (not values) from the summary.

**Impact**: The model can't reason about "I stored Acme's revenue as $500M" because that detail is gone. It must re-discover it via `memory_search` every time. This measures search ability, not memory management.

**Better alternative**: Gradual forgetting — keep last N messages or a sliding window. This is closer to how real agents work (context window limits ≠ complete amnesia).

### Problem 2: Storage Decisions Require Clairvoyance

In lite tier: 30 entities arrive, budget is 15. The model must choose which 15 to store — but questions haven't been asked yet.

The simulation's `entity_importance()` function knows the question distribution and ranks entities accordingly. Real models can't do this. They can only use heuristics like "store entities with more attributes" or "store entities mentioned in relationships."

**Impact**: The gap between simulation-optimal storage and model-achievable storage is large. This makes the evaluation partially measure luck rather than capability.

**Better alternative**: Show entity summaries upfront, then let the model choose which to store in detail. Or make questions only about entities that appear in the first N% of the stream (so early storage decisions are informed).

### Problem 3: ChromaDB Search Is a Black Box

The model stores `"Acme Corp | Revenue: $500M | Founded: 1995"` and later searches `"Acme Corp"`. Whether this returns the right entry depends on:
- Sentence-transformer embedding similarity
- The reranking heuristics in `ChromaDBBackend.search()`
- Whether the keyword fallback catches it

The model has no control over or insight into this process. If embedding similarity happens to rank a different entity higher, the model fails through no fault of its own.

**Impact**: Evaluation partially measures ChromaDB search quality, not model capability. Different ChromaDB versions or embedding models could change scores.

**Better alternative**: Exact key-value storage (entity name → data), or at minimum, document the search algorithm's behavior in the system prompt so the model can optimize its storage format.

### Problem 4: Efficiency Axis Design

```python
efficiency = min(correct_total / write_budget, 1.0)
```

This rewards correct answers per budget unit. But:
- A model that stores nothing (writes=0) and guesses 2 correct from context: efficiency = 2/15 = 0.133
- A model that wastes 10 writes on useless data but gets 3 correct: efficiency = 3/15 = 0.2

The axis doesn't penalize wasted budget — it only rewards correct answers. A model that stores efficiently and one that stores wastefully get the same efficiency score if they answer the same number of questions correctly.

**Better alternative**: `efficiency = correct_answers / max(writes_used, 1)` — rewards getting more from less.

---

## Part 3: Training Perspective — Why SFT Can't Solve MemoryGym

### The Fundamental SFT Paradox

SFT requires showing the model complete examples. But MemoryGym's context redaction creates an impossible choice:

| Approach | What Model Learns | Fatal Flaw |
|----------|-------------------|------------|
| Keep full history | Write, Edit, Search, Answer flow | Model answers from context, not memory (confirmed by GRPO v3 devlog) |
| Redact before questions | Search → Answer pattern | 0 Write, 0 Edit in training data — model never learns storage |
| Redact per-event (like eval) | Nothing useful | Each event is isolated, no learning signal |

**After 6 iterations of data generation, the best achievable SFT data has:**
- Full pipeline (Write + Edit + Search + Answer) — but model sees full context
- 89% grounded answers — but 11% are unverifiable from visible context
- Realistic ChromaDB results — but training search results may differ from eval

**Prior experimental evidence** (from devlog):

| Experiment | Data | Result | Root Cause |
|------------|------|--------|------------|
| SFT v2b | 480 simulation trajectories | 3/10 correct | Write token dominance, lost reasoning |
| SFT v3 | 480 new-format trajectories | 0/10 correct | Loss too low, memorized Write pattern |
| GRPO v3 | RL on SFT v3 base | 5/10 correct | Cheated by reading from context |

**SFT ceiling estimate: 4-6/10.** The remaining gap requires RL.

### Why RL Is Also Hard

MemoryGym has a RL environment (`MemoryEnv`) with shaped rewards. But:

1. **Sparse reward**: Only question events give reward signal. Storage/correction actions get reward only via shaped heuristics (F41/F43), not from actual downstream correctness.

2. **Long episodes**: 18+ events per episode, each requiring API calls. One rollout takes ~90 seconds with a real model. 1000 rollouts = 25 hours of API time.

3. **Credit assignment**: If a question is answered wrong, was it because:
   - Wrong entity stored? (ingest decision)
   - Correction not applied? (edit failure)
   - Wrong search query? (retrieval failure)
   - Wrong answer extraction? (reasoning failure)

   The reward signal doesn't distinguish these, making learning inefficient.

4. **GRPO v2 collapsed without KL** (devlog): Policy drifted to exploit advantage signal within groups rather than learning generalizable strategies. GRPO v3 with KL stayed stable but found the context-reading shortcut.

### The Training-Evaluation Gap

| What Eval Needs | What SFT Teaches | What RL Teaches |
|-----------------|-------------------|-----------------|
| Store selectively under budget | Store what simulation chose | Store what maximizes reward (but sparse signal) |
| Edit corrections via search | The Edit pattern (if not redacted) | Edit when reward improves (slow learning) |
| Search + extract specific values | Search → answer (with grounded reasoning) | Search → correct answer (trial and error) |
| Handle context reset gracefully | Either full context or no context | Context-reading shortcut |

---

## Part 4: Recommendations

### For MemoryGym as Evaluation

1. **Replace full redaction with sliding window**: Keep last 3-5 events instead of wiping everything. This is more realistic and enables SFT training that matches eval conditions.

2. **Make storage decisions informed**: Show entity names + brief descriptions upfront, then deliver detailed documents. This separates "what to prioritize" from "how to store."

3. **Fix Efficiency axis**: Use `correct / max(writes_used, 1)` instead of `correct / write_budget` to reward efficiency, not just correctness.

4. **Document search behavior**: Add search algorithm description to system prompt so models can optimize storage format for retrievability.

### For Training on MemoryGym

1. **SFT warm-start is necessary but not sufficient**: Use our v6 data (500 entries, full pipeline, 89% grounded) to teach tool format and basic patterns. Expected: 4-6/10.

2. **GRPO is the path to high scores**: Use MemoryEnv with shaped rewards. Key: prevent context-reading shortcut by increasing entity count or reducing max_length.

3. **Curriculum training**: Start with lite tier (30 entities), graduate to standard (60) and hard (120). Mem-alpha paper shows short-context RL generalizes to long-context.

4. **Two-phase approach**: Phase 1 = SFT to teach tools + format. Phase 2 = GRPO to learn strategy + reasoning. Don't skip Phase 1 — GRPO v2 showed RL alone leads to collapse.

### For the Leaderboard Decision

MemoryGym is a well-crafted evaluation that tests a genuinely important capability. However, its design makes it expensive to train for (RL required, ~$50+ per competitive model). If added to the Bittensor leaderboard, expect:
- Most competitors to plateau at 3-5/10 (SFT ceiling)
- Only teams investing in RL to break through to 7+/10
- High variance due to ChromaDB search non-determinism

---

## Appendix: Data Generation Lessons

Through 6 versions of SFT data generators, key lessons learned:

| Version | Change | Result | Lesson |
|---------|--------|--------|--------|
| v1 (old 499) | Mock tool results | All score=0 | Fake data teaches nothing |
| v2 | Real ChromaDB results | 71% grounded | Real tool output matters |
| v3 | Added reasoning chains | Template-y reasoning | "The answer is X" ≠ grounded reasoning |
| v4 | Context redaction | 0 Write, 0 Edit | Redaction kills storage training |
| v5 | Removed redaction | Full pipeline restored | Train-test mismatch accepted |
| v6 | Correction-grounded reasoning | 89% grounded | Reference correction events for delta/counterfactual |

The fundamental tension — keeping full context (needed for Write/Edit training) vs redacting (needed to match eval) — is unresolvable within SFT. This is not a data engineering problem; it's a limitation of the evaluation design.
