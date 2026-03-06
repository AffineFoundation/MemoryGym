# MemoryBench

Benchmark evaluating LLM agents' **memory management** ability — what to store, when to update, what to discard under write budget pressure.

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
# Run all tests
python -m pytest tests/ -q

# Quick iteration: world template tests
python tests/test_worlds.py

# Simulation invariant check
python -m memorybench.bench --seeds 10 --validate

# Real agent eval
python -m memorybench.bench --model openai/gpt-4o --seed 42 --template company

# Inspect AI real agent eval
inspect eval memorybench/worlds/eval_task.py -M openai/gpt-4o -T seed=42 -T template=company
```

**Rule**: Every code change must pass `python tests/test_worlds.py` before committing.

## Architecture

```
memorybench/
├── worlds/                 # WorldTemplate system
│   ├── base.py             # WorldTemplate ABC, World, EntitySpec, GeneratedQA
│   ├── company.py          # CompanyWorld: 600 names × 10 attrs × 12 sectors
│   ├── research.py         # ResearchWorld: 625 names × 10 attrs × 10 venues
│   ├── city.py             # CityWorld: 600 names × 10 attrs × 8 regions
│   ├── hospital.py         # HospitalWorld: 600 names × 10 attrs × 10 departments
│   ├── sport.py            # SportWorld: 600 names × 10 attrs × 10 leagues
│   ├── eval_task.py        # Inspect AI task: stream solver
│   └── eval_scorer.py      # 6-axis scorer
├── evaluation/
│   ├── validators.py       # Answer matching (exact → numeric → synthesis → abstention)
│   ├── llm_judge.py        # Multi-model LLM judge
│   └── backend_bench.py    # Backend ceiling benchmark (no LLM)
├── memory/
│   ├── budget.py           # MemoryBudget (write limit enforcement)
│   └── backends/
│       ├── chromadb_backend.py  # Vector search (default)
│       └── mem0_backend.py      # mem0 SDK wrapper (optional)
├── inspect_task/
│   └── tools.py            # Inspect AI memory tool wrappers
├── agents/
│   └── stream_agent.py     # Real LLM agent runner
├── simulation.py           # System self-testing (NOT evaluation)
└── bench.py                # CLI: real eval (--model) + simulation runner
```

## Evaluation vs Simulation

**Real evaluation** (measures agent ability):
- `bench.py --model <name>`: stream_agent + real LLM + real backend
- `inspect eval eval_task.py`: Inspect AI + real LLM + real backend

**Simulation** (`simulation.py`): system self-testing, **not** evaluation.
No LLM, no backend. Deterministic strategies verify scoring invariants:
- perfect=100%, guesser=0%, strategic>naive+10%, abstainer<20%, smart_guesser<5%

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
| Cross-domain evaluation | Tests cross-referencing, not storage decisions |
| All-max synthesis | Agent learns "always pick biggest" |
| Questions that change based on storage | Agent games by storing selectively |

## Memory Interface Principle

MemoryBench reuses mem0-compatible memory interface (store/search/get/forget/list). Models trained on standard memory APIs transfer directly to real agent systems.

## Cross-Backend Comparability

Scores are **not comparable** across different backends:
- **ChromaDB**: 1 `store()` = 1 memory entry (verbatim storage)
- **mem0**: 1 `store()` = N memory entries (LLM auto-extracts facts)

With the same `write_budget=30`, mem0 stores far more information than ChromaDB.
Only compare agents within the same backend.

## Autonomous Development Protocol

### Hard Stops (require human decision)
- Guesser > 5% after a change
- Perfect < 100% after a change
- Fundamental design assumption proven wrong

### Proceed Autonomously
- Test passes → next step
- Test fails with clear root cause → fix and re-run
- New hack vector found → add test, fix, verify
