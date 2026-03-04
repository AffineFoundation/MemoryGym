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
