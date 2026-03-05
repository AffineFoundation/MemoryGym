# MemoryBench

Benchmark evaluating LLM agents' **memory management** ability — what to store, when to update, what to discard under write budget pressure.

**Architecture**: WorldTemplate system (`memorybench/worlds/`). V3 streaming system (`domains/`, `generation/`, `simulation/`) is **deprecated** — do not invest in it.

**Core loop**: seed → WorldTemplate → generate entities → render documents → agent stores under budget → corrections mutate world → adaptive questions → 6-axis scoring.

**Key distinction**: Tests strategic storage decisions, not retrieval quality. Write-time is test-time.

## Design Principles

### Anti-Hack
- **Guesser = 0%**. Every validator/scorer change must be tested against guesser.
- **Synthesis** answers require `"EntityName (value)"` — both entity match (≥67% word overlap) AND numeric match (adaptive tolerance).
- **Update questions use identical `_q_text` as retrieval** → cannot distinguish by wording.
- **Abstention uses fictitious entities with active attributes** → cannot distinguish from retrieval.
- **Bidirectional synthesis** (max + min) → no "always pick biggest" heuristic.
- **detect_stored_entities requires name + value** → name-only packing = 0 coverage.
- **V14 integer-exact tolerance**: Integer GT requires exact match (blocks year/count guessing). Float GT uses 2% relative tolerance.
- **Trick retrieval** (~2/seed): Real entity, retrieval phrasing. Always-abstain strategy fails these.
- **eval_salt**: `--eval-salt N` perturbs numeric values, invalidating pre-computed answers for a given seed.
- **Abstainer ceiling**: Always-abstain scores ≤15% (only abstention questions).

### Real Evaluation
- **No fallback**: Missing data or failed computation must raise, never `or 0` / `or "N/A"` / `except: return default`. Never chain validator A → fallback to B. Each validation path (rule-based OR LLM judge) must be self-contained.
- **GT from World state**: Ground truth computed from world entities after corrections. No external data.
- **Deterministic validation**: Rule-based matching for simulation. LLM judge (multi-model, hardcoded) for real agent evaluation.

### Reproducibility
- **Same seed → identical scenario**. Entity generation, documents, corrections, questions — all deterministic.
- **Corrections mutate World in place** → GT is always the current (corrected) value.

## Development Rules

1. **Occam's Razor**: Minimum code to solve the problem. No premature abstractions.
2. **Root Cause Fix**: Never patch symptoms. Trace the bug to its origin and fix there.
3. **File Size**: Each `.py` file ≤ 1000 lines.
4. **No Fallback**: Zero tolerance for silent error masking. If data is missing, raise explicitly.
5. **Import Style**: Relative within `memorybench/` package, absolute for cross-package.
6. **Commit Messages**: Concise one-liner. Describe the *why*, not the *what*. **Never add Co-Authored-By, Generated-by, or any metadata lines** — message body must be empty. **Only commit when explicitly asked** — never auto-commit.
7. **Test Before Ship**: New logic → add test to `test_worlds.py` first.

## Development Flywheel

```bash
# Quick iteration: run all world template tests
python tests/test_worlds.py

# Single seed simulation
python -c "from tests.test_worlds import run_evaluation; run_evaluation(seed=0)"

# Multi-seed aggregate
python -c "from tests.test_worlds import run_multi_seed; run_multi_seed(10)"

# Inspect AI real agent eval
inspect eval memorybench/worlds/eval_task.py -M openai/gpt-4o -T seed=42 -T template=company
```

**Rule**: Every code change must pass `python tests/test_worlds.py` before committing.

## Architecture

```
memorybench/
├── worlds/                # PRIMARY evaluation system
│   ├── base.py            # WorldTemplate ABC, World, EntitySpec, GeneratedQA
│   ├── company.py         # CompanyWorld: 600 names × 10 attrs × 12 sectors
│   ├── research.py        # ResearchWorld: 625 names × 10 attrs × 10 venues
│   ├── city.py            # CityWorld: 600 names × 10 attrs × 8 regions
│   ├── eval_task.py       # Inspect AI task: 3-phase solver (INGEST→CORRECTIONS→QUESTIONS)
│   └── eval_scorer.py     # 6-axis scorer (accuracy, storage, maintenance, reasoning, efficiency, process)
├── evaluation/
│   ├── validators.py      # 4-layer answer matching (exact → numeric → synthesis → abstention)
│   └── llm_judge.py       # Optional LLM fallback judge
├── memory/
│   ├── budget.py          # MemoryBudget (write limit enforcement)
│   ├── backends/
│   │   ├── mock_backend.py    # Substring search (for testing/simulation)
│   │   └── chromadb_backend.py # Vector search (for real evaluation)
│   ├── store.py           # MemoryStore (legacy, used by V3 simulation)
│   └── mcp_server.py      # FastMCP server
├── inspect_task/
│   └── tools.py           # Inspect AI memory tool wrappers
├── agents/
│   └── llm_agent.py       # Real LLM agent runner (text-based tool calling)
├── tests/
│   └── test_worlds.py     # 21 invariant + quality tests
│
├── [DEPRECATED] domains/  # V3 streaming — do not modify
├── [DEPRECATED] generation/ # V3 task stream — do not modify
├── [DEPRECATED] simulation/ # V3 simulation agents — do not modify
├── [DEPRECATED] cli.py    # V3 CLI — do not modify
└── [DEPRECATED] config.py # V3 config — do not modify
```

## WorldTemplate Three Evaluation Axes

**Axis 1 — Storage breadth** (retrieval questions): Did you store this entity?
**Axis 2 — Memory maintenance** (update questions): Did you apply the correction?
**Axis 3 — Reasoning** (comprehension questions): Can you compute from stored data?
**Axis 0 — Volume pressure**: 200+ entities, limited budget → must be selective.

### Question Budget (with corrections)

| Purpose | Budget | Tests |
|---------|--------|-------|
| Retrieval | 40% | Storage breadth |
| Update | 20% | Memory maintenance |
| Comprehension | 25% | Multi-entity reasoning |
| Abstention | 15% | Knowledge boundaries |

### Validated Baseline (10 seeds, 60 entities, 20 questions, 5 corrections)

| Strategy | Accuracy | Retrieval | Update | Comprehension | Abstention |
|----------|----------|-----------|--------|---------------|------------|
| perfect  | 100%     | 100%      | 100%   | 100%          | 100%       |
| strategic| 64%      | ~76%      | 62%    | 26%           | 100%       |
| naive    | 37%      | ~48%      | **0%** | 14%           | 100%       |
| guesser  | 0%       | 0%        | 0%     | 0%            | 0%         |

## Roadmap

See `ROADMAP.md` for phased development plan.

Current phase: **Phase 0 (Consolidation)** — unify on WorldTemplate, remove V3 entry points.

## Dead Ends — Do Not Repeat

| Approach | Why It Failed |
|----------|--------------|
| Fixed question pool + fixed answers | Memorizable |
| Small entity set (< 100) | Enumerable; model can memorize all pairs |
| Structured format as needle | 100% classifiable; agent skips reading |
| WikiText as filler/background | Perplexity uncontrollable |
| Different phrasing per question type | Phrasing attack: detect type by wording |
| Read-all-then-answer-all (pure) | Tests RAG retrieval, not memory management |
| Narrative document padding (~1500 chars) | Trivially extractable by LLMs |
| V3 streaming `_balance_distribution` | 200-line ad-hoc fixups, 11.8% retrieval |
| V3 pre-generated questions | Not adaptive to storage behavior |
| V3 update questions with distinct phrasing | "recently revised" detectable |
| Cross-domain evaluation | Tests cross-referencing, not storage decisions |
| All-max synthesis | Agent learns "always pick biggest" |
| Questions that change based on storage | Agent games by storing selectively |

## Memory Interface Principle

MemoryBench reuses mem0-compatible memory interface (store/search/get/forget/list). Models trained on standard memory APIs transfer directly to real agent systems.

## Autonomous Development Protocol

When developing without human input, follow these rules:

### Hard Stops (require human decision)
- Guesser > 5% after a change
- Perfect < 100% after a change
- Fundamental design assumption proven wrong

### Proceed Autonomously
- Test passes → next step
- Test fails with clear root cause → fix and re-run
- New hack vector found → add test, fix, verify
- Phase gate passed → start next phase

### Flywheel (Phase 3+)
```
RUN eval → ANALYZE results → IDENTIFY hack vector →
ADD test → FIX vulnerability → VERIFY all tests pass → REPEAT
```
