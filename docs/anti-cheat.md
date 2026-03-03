# MemoryBench v3 — Anti-Cheat Design

## 1. Threat Model

| Threat | Description |
|--------|-------------|
| **Pre-memorization** | Answers exist in training data |
| **Pattern matching** | Template structure leaks answer type |
| **Shortcutting** | Skip reading documents, guess answers |
| **Phrasing attack** | Distinguish question types from wording alone |
| **Seed fingerprinting** | Map seed → known answers |
| **Prompt injection** | Manipulate evaluation via injected instructions |
| **Strategy memorization** | Fixed storage strategy works across all seeds |

## 2. Defense Matrix

### Anti-Memorization

| Mechanism | Effect |
|-----------|--------|
| **NamePool** | 36 prefixes x 20 suffixes = 720 first names, 35 x 20 = 700 last names → **504K unique full names** |
| **Per-entity combinatorics** | 504K names x attributes x skills → ~1.56 trillion per person |
| **Multi-domain variable schema** | Each seed selects 3-5 of 6-8 attributes per domain → 182+ schema variants |
| **Dynamic numeric values** | Salaries, budgets, metrics generated per seed from continuous ranges |
| **Seed space** | 2^32 seeds x combinatorial entity space → astronomically large |

**Result**: 200-person scenario has >10^2439 possible universes. Cross-seed GT overlap = 0%.

### Anti-Phrasing Attack

All question types use **unified phrasing** — no stylistic markers distinguish retrieval from abstention. The agent cannot determine question type from wording alone.

**Trick retrieval**: Questions phrased like abstention ("Do you have information about X's Z?") but the answer is a real value stored in memory. Defeats always-abstain strategies. ~2 trick questions per seed.

### Anti-Strategy Memorization

| Mechanism | Effect |
|-----------|--------|
| Variable schema | Each seed activates different attribute subsets |
| Distractor entities | 3-8 Projects + 3-6 Meetings mixed in |
| Variable question distribution | Question type weights differ per seed |
| Multi-domain switching | Domain B introduced mid-stream |
| Eval salt | Optional perturbation prevents seed fingerprinting |

### Anti-Shortcutting

| Mechanism | Effect |
|-----------|--------|
| Process score | Tracks `searched_before_answering` |
| Budget pressure | 30 writes for ~40 entities forces selective storage |
| Cross-domain questions | Require data from both domains |
| Synthesis questions | Require aggregation across multiple entities |

### Anti-Prompt Injection

XML sandboxing isolates document content from system instructions.

## 3. Guesser Baseline

The **guesser** agent provides a blind-guessing baseline — no memory tools used, no documents read:

| Answer Type | Guesser Strategy | Hit Rate |
|-------------|-----------------|----------|
| Numeric | Random from plausible range | ~55% attempted |
| Entity name | Random from common names | ~30% attempted |
| Abstention | Random abstain | ~15% attempted |

**Measured result (30 seeds)**: guesser accuracy = **2.1%** (target: <5%)

Critical: guesser scores **0%** on synthesis and cross-domain questions because the answer format `"EntityName (value)"` requires matching both entity name and numeric value.

### Entity Matching

Word-overlap based matching (>=50% GT keywords). Strips titles and parentheticals before comparison. Prevents partial-name gaming.

## 4. Validation Results (30 Seeds)

| Strategy | Accuracy | Trajectory | Efficiency | Adaptability | Process |
|----------|----------|------------|------------|--------------|---------|
| perfect | 100.0% | 0.500 | 0.356 | 1.000 | 0.88 |
| strategic | 99.7% | 0.497 | 0.997 | 1.000 | 0.96 |
| fixed | 83.1% | 0.420 | 0.832 | 1.000 | 0.95 |
| naive | 42.4% | 0.384 | 0.424 | 0.878 | 0.72 |
| guesser | 2.1% | 0.507 | 0.467 | 0.093 | 0.00 |

**100-seed stability**: perfect 100.0% +/- 0.00%, strategic 99.8% +/- 0.95%, guesser 2.2% +/- 2.91%

## 5. 17-Point Validation Checklist

All checks must PASS:

1. Perfect agent accuracy = 100%
2. Strategic > naive + 10%
3. Guesser accuracy < 5%
4. Guesser synthesis accuracy = 0%
5. Guesser cross-domain accuracy = 0%
6. Guesser process score = 0
7. Determinism: same seed → same scenario
8. Global ID uniqueness across all tasks
9. Entity match uses word-overlap (>=50%)
10. Trick retrieval questions present (~2/seed)
11. Perfect/strategic score 100% on trick retrieval
12. Guesser scores 0% on trick retrieval
13. Abstention questions present
14. Variable schema across seeds
15. Seed required (ValueError if None)
16. No fallback values in GT computation
17. Answer format enforced for synthesis/cross-domain
