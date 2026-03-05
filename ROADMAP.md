# MemoryBench Development Roadmap

**Goal**: A hack-proof, valuable open-source memory management evaluation system.

**Decision**: WorldTemplate (`worlds/`) is the sole evaluation path. V3 streaming (`domains/` + `generation/` + `simulation/`) is deprecated — it has structural anti-hack violations (update question phrasing, pre-generated questions, retrieval underrepresentation).

## Current State (Validated — 30 seeds × 5 templates × 6 strategies)

- WorldTemplate: 5 templates (company/research/city/hospital/sport), 122 tests passing
- Baselines: perfect=100%, strategic=63-65%, naive=18-19%, guesser=0%
- Attack strategies: abstainer=15%, smart_guesser=0-1%
- Update differentiation: strategic=70%, naive=0% (the maintenance axis works)
- Inspect AI integration: `worlds/eval_task.py` runs interleaved stream evaluation
- Anti-hack: V14 integer-exact + float-2% tolerance, trick retrieval, eval_salt
- 55 validation checks: ALL PASS

## Phase 0: Consolidation ✅

Completed: `bench.py` is the unified CLI with simulation + model eval modes.

## Phase 1: Streaming Interleave ✅

Completed: `generate_stream()` interleaves ingest/correction/question events.
~40% of questions emitted mid-stream, corrections at 60% mark.

## Phase 2: Real Agent Harness ✅

Completed: `stream_agent.py` uses text-based `<tool_call>` protocol.
`bench.py --model <name>` runs real LLM evaluation.
Inspect AI integration in `eval_task.py` with nuclear redaction.

## Phase 3: Anti-Hack Hardening ✅

Completed flywheel iterations:
- V14: Integer-exact, float-2% tolerance (kills year/count guessing)
- Trick retrieval: defeats always-abstain strategy
- eval_salt: perturbs values to invalidate pre-computed answers
- Smart guesser validation: midpoint/quartile guessing < 5%
- 6 strategies tested: perfect, strategic, naive, guesser, abstainer, smart_guesser

Remaining attack surfaces to monitor:
- Prompt injection via correction notices
- Budget gaming (1 write = compressed index)
- Context window exploitation (nuclear redaction in place but untested with real models)

## Phase 4: Multi-Template Evaluation ✅

5 templates: company, research, city, hospital, sport.
Cross-template variance < 3% (strategic: 63-65% across all templates).
55 validation checks ALL PASS across 30 seeds.

## Phase 5: Open Source Release (IN PROGRESS)

Steps:
1. ✅ `pyproject.toml` with console script entry point
2. ⬜ README.md with clear usage instructions
3. ⬜ Leaderboard format (JSON schema for results)
4. ⬜ GitHub Actions CI (run tests + validation on every PR)
5. ⬜ Example evaluation scripts
6. ⬜ Remove V3 legacy code (`domains/`, `generation/`, `simulation/`)
7. ⬜ Write paper/blog post

---

## Decision Rules (for autonomous development)

These rules allow continuous development without human intervention:

### When to proceed vs stop

| Situation | Action |
|-----------|--------|
| Test passes | Proceed to next step |
| Test fails, root cause is clear | Fix and re-run |
| Test fails, root cause unclear | Add diagnostic logging, investigate for max 30 min, then try alternative approach |
| Invariant violation | STOP — this means a design assumption is wrong. Write diagnosis to `ROADMAP.md` Dead Ends section |
| Guesser > 5% | STOP — anti-hack is broken. Fix before any other work |
| Perfect < 100% | STOP — evaluation logic is broken. Fix before any other work |

### When to commit

- After each Phase gate passes
- After each flywheel iteration (test added + fix verified)
- After any refactor that changes > 3 files

### Code quality gates

- Every `.py` file < 1000 lines
- No `or 0`, `or "N/A"`, `except: return default`
- No fallback values — raise explicitly on missing data
- Run `python tests/test_worlds.py` after every change

### What NOT to do

- Don't add features beyond current phase
- Don't refactor code that isn't in the current phase's scope
- Don't add cross-domain evaluation (dead end per CLAUDE.md)
- Don't add narrative padding to documents (dead end per CLAUDE.md)
- Don't create custom memory interfaces — use mem0-compatible API
- Don't optimize for LLM cost — correctness first

---

## Dead Ends Log

Record failed approaches here to prevent repetition.

| Date | Approach | Why It Failed |
|------|----------|---------------|
| (pre-existing) | V3 streaming update questions with distinct phrasing | Models detect "recently revised" → classify without reading corrections |
| (pre-existing) | V3 pre-generated questions (before storage) | Questions don't adapt to what agent stored → unfair evaluation |
| (pre-existing) | V3 _balance_distribution (200-line ad-hoc fixups) | Over-engineered, fragile, produces 11.8% retrieval |
