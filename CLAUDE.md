# MemoryBench v3

Benchmark evaluating LLM agents' **memory management** ability — what to store, when to update, what to discard under write budget pressure.

**Core loop**: seed → 2 domains (from 3) → 25 entities/domain → 25-task stream with interleaved docs+questions → agent uses MCP memory tools → 4-dimension scoring (accuracy, trajectory, efficiency, adaptability).

**Key distinction**: Tests strategic storage decisions, not retrieval quality. Write-time is test-time. Unlike RAG benchmarks, the agent must be selective about what enters memory.

## Design Principles

### Anti-Hack
- **Guesser baseline must stay < 5%** (currently 2.1%). Every validator change must be tested against guesser.
- **Synthesis/cross_domain** answers require format `"EntityName (value)"` — both entity match (≥50% word overlap) AND numeric match (±5%). Guessing one without the other = 0%.
- **Trick retrieval** (~2/seed): Phrased like abstention but GT is a real value. Defeats always-abstain strategies.
- **504K NamePool**: 720 first × 700 last names. Combinatorial space makes pre-memorization impossible.
- **eval_salt**: `--eval-salt N` perturbs numeric values, invalidating pre-computed answers for a given seed.
- **Unified phrasing**: All question types use identical sentence structure. Cannot distinguish type by wording.

### Real Evaluation
- **No fallback**: Missing data or failed computation must raise, never `or 0` / `or "N/A"` / `except: return default`.
- **GT from KB**: Ground truth computed directly from generated knowledge base. No external data source.
- **Deterministic validation**: Every answer is verifiable by rule-based matching (LLM judge is optional fallback only).

### Reproducibility
- **Same seed + same eval_salt → identical scenario**. Domain selection, entity generation, task ordering, questions — all deterministic.
- **global_id**: `seed * n_tasks + task_id`. Must be unique across all seeds. Verified by validation check #17.
- **Determinism check**: Validation check #16 runs same seed twice and compares outputs.

## Development Rules

1. **Occam's Razor**: Minimum code to solve the problem. No premature abstractions.
2. **Root Cause Fix**: Never patch symptoms. Trace the bug to its origin and fix there.
3. **File Size**: Each `.py` file ≤ 1000 lines.
4. **No Fallback**: Zero tolerance for silent error masking. If data is missing, raise explicitly.
5. **Import Style**: Relative within `memorybench/` package, absolute for cross-package.
6. **Commit Messages**: Concise one-liner. Describe the *why*, not the *what*. **Never add Co-Authored-By, Generated-by, or any metadata lines** — message body must be empty. **Only commit when explicitly asked** — never auto-commit.
7. **Test Before Ship**: New validator logic → add test to `test_validators.py` first.

## eval.py Development Flywheel

```bash
# Quick iteration: single seed, verbose output
python eval.py --seed 0 -v

# Stability check: 5 seeds + 17-point validation
python eval.py --seeds 5 --validate

# Release gate: 30 seeds + validation + JSON output
python eval.py --seeds 30 --validate -o results.json

# Subset strategies (faster iteration)
python eval.py --seed 0 --strategy strategic guesser -v

# Anti-fingerprint test
python eval.py --seed 0 --eval-salt 42 --validate
```

**Rule**: Every code change must pass `--seed 0 -v` before committing. Every release must pass `--seeds 30 --validate`.

## Architecture Quick Reference

```
memorybench/
├── cli.py                 # CLI entry, aggregation, validation (17 checks)
├── config.py              # EvalConfig defaults (25 tasks, 50 writes, 2 domains)
├── domains/
│   ├── base.py            # Domain ABC, Entity/QA/Task types, question generators
│   ├── organization.py    # Person entities (salary, age, performance...)
│   ├── research.py        # Researcher entities (citations, h_index, funding...)
│   ├── logistics.py       # Warehouse/Route entities (capacity, throughput...)
│   └── names.py           # 504K name generator
├── generation/
│   ├── scenario.py        # select_domains(seed) → 2 of 3 domains
│   ├── task_stream.py     # generate_stream() → 25 tasks with phased domains
│   └── questions.py       # Per-competency question generators
├── simulation/
│   └── agents.py          # 5 strategies: perfect/strategic/fixed/naive/guesser
├── evaluation/
│   ├── validators.py      # 5-layer matching (exact → numeric → synthesis → abstention)
│   ├── scorer.py          # 4D scoring (accuracy, trajectory, efficiency, adaptability)
│   └── llm_judge.py       # Optional LLM fallback
├── memory/
│   ├── store.py           # MemoryStore (substring search for simulation)
│   └── mcp_server.py      # FastMCP server (5 tools: write/search/update/delete/list)
└── inspect_task/
    ├── task.py            # Inspect AI task (seed required, no default)
    ├── solver.py          # Sequential streaming solver
    ├── scorer.py          # 4D scorer + per-competency breakdown
    └── tools.py           # MCP tool wrappers (write costs 1, search/delete free)
```

**Data flow**: `select_domains(seed)` → `generate_kb()` per domain → `_perturb_kb()` if eval_salt → `_plan_updates()` → `_build_tasks()` → `_balance_distribution()` → 25 tasks with phased competency distribution.

**Task phases**: 0-9 Domain A intro → 10-11 Domain A deepening → 12-19 Domain B switch → 20-24 Pressure (mixed, cross-domain).

**Competency distribution** (per 25 tasks): ~10 retrieval, ~6 synthesis, ~3 update, ~3 abstention, ~2 cross_domain, ~2 trick_retrieval.

## Memory Interface Principle

MemoryBench should reuse memory interfaces from mainstream agent frameworks (e.g., OpenClaw) rather than inventing custom ones. Models trained on a bespoke interface have no practical value — their memory skills must transfer directly to real agent systems.

## Dead Ends — Do Not Repeat

| Approach | Why It Failed |
|----------|--------------|
| Fixed question pool + fixed answers | Memorizable (~3K Q&A pairs in v1) |
| Small entity set (< 100) | Enumerable; model can memorize all pairs |
| Structured format as needle (`Name: X, Salary: Y`) | 100% classifiable; agent skips reading |
| WikiText as filler/background | Perplexity uncontrollable; difficulty variance unrelated to memory |
| Fixed 6-competency categories | Too rigid; questions span multiple categories or fit none |
| Different phrasing per question type | Phrasing attack: "hedging = abstain" without reading docs |
| Read-all-then-answer-all | Tests RAG retrieval, not memory management. No selectivity pressure |

## Testing

Two modes, use both as needed:

1. **eval.py integration**: Run `eval.py` to generate results, then **thoroughly analyze the output** — strategy separation, guesser ceiling, competency breakdown, cross-domain accuracy. Judge whether results align with project design intent (anti-hack, real evaluation, reproducibility), not just whether numbers look okay.
2. **Unit tests**: Write targeted tests in `tests/` for isolated logic (validators, entity matching, scoring math). Use pytest for fast iteration on specific components before running full eval.

---

## WorldTemplate System (`memorybench/worlds/`)

Evaluation abstraction that tests three dimensions of memory management:
1. **Storage**: what to keep under budget pressure (volume >> budget)
2. **Maintenance**: whether corrections are applied to stored data
3. **Retrieval**: whether stored data supports reasoning (synthesis, aggregation, conditional)

### Core Flow

```
WorldTemplate.generate_world(seed) → World (entities + attrs)
    ↓ render_document() → narrative docs (~1500 chars each, volume >> budget)
    ↓ agent stores under write budget → must compress
    ↓ generate_corrections() → correction notices → agent updates memory
    ↓ detect_stored_entities() → stored/missed sets
    ↓ gen_adaptive_questions(corrections=...) → questions + GT (from mutated World)
```

- `WorldTemplate` (ABC): entity schema, narrative rendering, question generation
- `CompanyWorld`: 600 names × 10 attrs × 12 sectors
- `ResearchWorld`: 625 names × 10 attrs × 10 venues
- `CityWorld`: 600 names × 10 attrs × 8 regions
- `World`: mutable deterministic state. Corrections update entity values in place.

### Three Evaluation Axes

**Axis 1 — Storage breadth** (retrieval questions): Did you store this entity?
- Retrieval from full pool, deduped by entity and attribute
- Stored ratio directly determines retrieval accuracy

**Axis 2 — Memory maintenance** (update questions): Did you apply the correction?
- Update questions use identical `_q_text` as retrieval → agent cannot distinguish them
- GT is the CORRECTED value. Answering with old value = wrong.
- Strategic applies corrections → scores. Naive ignores → fails.
- Same storage rate, 10-15pp accuracy difference purely from update behavior.

**Axis 3 — Reasoning over stored data** (comprehension questions): Can you compute from stored data?
- Synthesis, aggregation, conditional require multiple entities in memory
- Tests whether storage is organized enough for multi-entity queries

**Axis 0 — Volume pressure** (entity quantity): Can you decide what to store?
- Compact documents ~250 chars/entity (pure key-value data, no padding)
- 200 entities → ~50K chars of data. Write budget forces selective storage.
- Agent must decide WHICH entities/attributes to keep, not HOW to parse prose.
- This axis is tested by real agents, not by simulation (simulation uses binary storage).

### Question Budget (with corrections)

| Purpose | Budget | Tests |
|---------|--------|-------|
| Retrieval | 40% | Storage breadth |
| Update | 20% | Memory maintenance |
| Comprehension | 25% | Multi-entity reasoning |
| Abstention | 15% | Knowledge boundaries |

Without corrections: retrieval 50%, comprehension 40%, abstention 10%.

### Anti-Hack Properties

1. Recall, coverage, and update questions use same `_q_text` → wording indistinguishable
2. Questions are seed-deterministic, storage-independent — only purpose tags adapt
3. Corrections mutate World state → GT is always the current value
4. Store more → monotonically better (0 violations across all ratios/seeds)
5. Narrative filler is structurally identical for all entities → no format signal
6. Synthesis bidirectional (max + min) → no "always pick biggest" heuristic

### Iteration Flywheel

1. **Run** `python tests/test_worlds.py` — 12 tests
2. **Invariant checks**:
   - Strategy ordering: perfect > strategic > naive > guesser
   - Guesser = 0%, perfect = 100%
   - Monotonicity: storing more never decreases accuracy
   - Determinism: same seed → identical questions and answers
   - Generality: all templates pass invariants
3. **Quality checks**:
   - Retrieval entity uniqueness ≥ 90%
   - Synthesis direction diversity (max + min)
   - Update questions present when corrections exist
   - Update differentiation: strategic > naive on update questions
   - Document volume ≥ 250 chars/entity, ≥ 50K chars at 200 entities
4. **Diagnose** any violation → root cause fix
5. **Record** findings below

### Validated Baseline (10 seeds, 60 entities, 20 questions, 5 corrections)

| Strategy | Accuracy | Retrieval | Update | Comprehension | Abstention |
|----------|----------|-----------|--------|---------------|------------|
| perfect  | 100%     | 100%      | 100%   | 100%          | 100%       |
| strategic| 64%      | ~76%      | 62%    | 26%           | 100%       |
| naive    | 37%      | ~48%      | **0%** | 14%           | 100%       |
| guesser  | 0%       | 0%        | 0%     | 0%            | 0%         |

Key: naive update = **0%** despite storing 40% of entities. This is the maintenance axis.

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| Compact documents (~250 chars) + many entities (200+) | Volume pressure from entity quantity, not prose filler. Compact format has no exploitable patterns. 200 entities × 250 chars = 50K chars of pure data. |
| Corrections mutate World state | GT must reflect corrected values. Agent answering with old value = wrong. Tests whether memory is maintained, not just created. |
| Update questions use same `_q_text` as retrieval | If update questions had distinct wording, agent could guess "this is about a correction" without actually reading corrections. Identical wording = must have real memory. |
| Strategies model update behavior, not just storage | Storage ratio alone doesn't differentiate memory quality. Update behavior is an independent axis: same storage rate, different accuracy. |
| Retrieval from full pool with dedup | Uniform sampling + entity/attr dedup tests breadth. Birthday problem without dedup causes 3× repeats. |
| Synthesis bidirectional | All-max lets agent always pick largest. Bidirectional requires genuine comparison. |
| Aggregation capped at 4, `agg_ops` constrained | Uncapped groups → no differentiation at high n. Rate attrs → average only ("total crime rate" is wrong). |
| Question budget adapts to corrections | With corrections: 40/20/25/15. Without: 50/40/10. Update budget scales with correction count. |

### Dead Ends

| Approach | Why It Failed |
|----------|--------------|
| Short documents (~50 tokens/entity) | Total volume 3.5K tokens for 60 entities. Fits in any context window. Memory tools unnecessary. |
| Binary coverage as sole evaluation axis | All question types reduce to "is entity stored?" → no differentiation between storage quality, organization, or maintenance. |
| No corrections/temporal dimension | Without corrections, system tests storage but not management. "Memory management" requires managing changes. |
| Questions that change based on storage | Agent could game by storing selectively. Fixed questions = Nash equilibrium. |
| Recall/coverage split from separate pools | Made 70% and 40% storage produce identical mixes. Full-pool sampling is correct. |
| All-max synthesis | Agent learns "always pick biggest" → no comprehension tested. |
| Narrative document padding (~1500 chars/entity) | Formulaic template "The recorded {label} for {name} is {value}, [filler]" is trivially extractable by LLMs. Model learns pattern after one document and strips all filler. Creates fake difficulty, not real compression pressure. |
