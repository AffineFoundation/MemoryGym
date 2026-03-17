# memorybench-arena — Universal Rules (auto-loaded every request)

## Loop Flow (MANDATORY)

1. `git pull --rebase`
2. **`cat` and read**: ROLE.md, inbox/*, memory/short-term.md (EVERY loop, do NOT rely on memory)
   Also read (every 5 loops or when notified): blueprint.md, status.md, shared/decisions.md
3. Process inbox (P0 immediately, P1 within 2 loops) → move to inbox/processed/
4. Execute role work
5. Write outputs (ALL mandatory, do in one step):
   - `memory/short-term.md` — Done / Blockers / In-progress / Next focus
   - `metrics.log` — append CSV: `timestamp,duration_s,tasks_done,errors,inbox_processed`
   - `heartbeat.json` — write `{"ts": <unix_ms>}` (server uses this to detect brain-dead roles)
   - `todo.md` — mark completed, add new
6. `git add <own files only>` → commit → `git pull --rebase` → push

Idle? Write "No tasks, idle". 3× idle → light mode (inbox + memory/metrics only).
**Light mode: do NOT git commit/push.** Only commit when you actually changed code or processed inbox.

## Git

- Commit: `{type}({scope}/{role}): {description}`
- **NEVER**: `git add -A`, `git add .`, `rm -rf`, `git push --force`, `git reset --hard`
- **NEVER** start background processes
- All committed content English. User-facing replies follow user's language.
- File > 500 lines → split

## Communication

- Inbox: `YYYYMMDDTHHMM_from_topic.md`, frontmatter: from/to/priority/type/date
- P0/P1 done → `type: ack, status: done` to sender
- Cross-role via lead (except P0 direct + bug fix direct)

## Shared Docs

- blueprint.md / status.md: lead only writes
- shared/decisions.md: append-only
- project.yaml: Server API only writes

## Self-Evolution

Every 10 loops: self-audit ROLE.md — delete dead rules, merge duplicates.
Also: delete LTM entries that contradict CLAUDE.md, ROLE.md, or decisions.md.
Quality gate: (a) what problem? cite metrics (b) what behavior changes? wording-only = skip (c) how to measure?
Proposal → lead inbox with metrics evidence → log to evolution.log.

---

# Project-Specific Rules

# MemoryGym

Build a **realistic, cheat-proof, training-valuable** LLM memory management evaluation and training platform.

Core constraints (inviolable — any code change must satisfy all simultaneously):

1. **Cheat-proof**: No strategy based on memorizing questions, patterns, or exploiting loopholes can achieve a high score
2. **WYSIWYG**: Scores reflect true capability — no shortcut paths exist
3. **Realistic scenarios**: Close to real agent memory scenarios (information overload + limited budget + outdated information needing updates)
4. **Trainable**: Not just an evaluation tool, but also an RL training environment (MemoryEnv)
5. **Deterministic**: Same seed → identical scenario and scoring

**Core pipeline**: seed → WorldTemplate → generate entities → render documents → agent stores within budget → correction events change world state → adaptive questioning → 4-axis scoring.

## Design Principles

### Scoring Validity

Scores must only reflect true memory management capability. Any strategy that doesn't understand content or make genuine storage decisions must not achieve a high score.

Validated via 9 simulation strategies: after every change to scoring or question logic, must satisfy perfect=100%, guesser=0%, smart_guesser<=5%, abstainer<15%, strategic>naive+10%.

### Memory Capability Definition

The "memory capability" evaluated and trained by this system is a composite ability, encompassing the full chain:

**Information Intake → Storage Decisions → Storage Organization → Retrieval & Locating → Change Tracking → Memory Reasoning → Metacognition**

- **Information Intake**: Extracting key information from unstructured documents
- **Storage Decisions**: Deciding what's worth remembering, how much, and at what granularity under budget constraints
- **Storage Organization**: Choosing storage format and granularity to make information both compact and retrievable
- **Retrieval & Locating**: Using correct query strategies to find stored information
- **Change Tracking**: Correctly updating existing memories when information changes
- **Memory Reasoning**: Computing and deriving answers from stored data
- **Metacognition**: Accurately judging what one knows and doesn't know

Evaluation design and difficulty tuning must serve this complete chain — it must not degrade to testing only one link.

### Training Value Constraint

Capabilities trained under the evaluation mechanism must have real-world transfer value. Any evaluation design change or difficulty adjustment must pass this test:

- **Has transfer value**: Genuine capability improvement in each link of the chain
- **No transfer value**: Adapting to specific infrastructure characteristics, exploiting evaluation system loopholes
- **Difficulty principle**: Reasonable difficulty enables continued progress after training; unreasonable difficulty yields scores with no real-world significance. Infrastructure quality should not become the evaluation bottleneck
- **Prompt neutrality**: System prompts should describe tasks and tools, not prescribe storage strategies. Storage strategy itself is part of the capability being tested

### Authentic Evaluation

- **No fallback**: Missing data or computation failures must raise exceptions — `or 0` / `or "N/A"` / `except: return default` are forbidden
- **GT from world state**: Ground truth is computed from corrected entities, no external data
- **Deterministic verification**: Simulations use rule matching; real evals use multi-model LLM judges

## Development Rules

1. **Occam's Razor**: Minimum code to solve the problem — no premature abstraction
2. **Root cause fix**: No patching — trace back to root cause and fix there
3. **File size**: Single `.py` file ≤ 1000 lines
4. **No Fallback**: Silent error masking is not allowed — missing data must be explicitly raised
5. **Import style**: Relative imports within `memorygym/`, absolute imports across packages
6. **Commits**: Describe why, not what. **Prohibit** Co-Authored-By, Generated-by, and other metadata lines. **Only commit when the current development task reaches a milestone**. Use `git add <specific files>`, not `git add -A`
7. **Test before commit**: New logic → add tests first
8. **Version number**: Update `memorygym/__init__.py` `__version__` with each Phase commit (patch increment, e.g., 0.4.0→0.4.1). Eval JSON extra automatically includes the version number to distinguish evaluation data across iterations

## Common Commands

```bash
python -m pytest tests/ -q -m "not slow"      # Fast tests (389 tests, ~60s)
python -m pytest tests/ -q                    # Full test suite (438 tests, ~7min)
python tests/test_worlds.py                    # World template tests (fast iteration)
python -m memorygym.bench --seeds 10 --validate  # Simulation invariant check
python -m memorygym.bench --model xxxxxx --seed 42 --template company  # Real evaluation
python -m memorygym.training data --seeds 5 --templates company       # SFT training data generation
```

Every code change must pass `python tests/test_worlds.py`.

## Evaluation System

**4-axis scoring** (budget pressure: entity count far exceeds write budget — selective storage is required):

| Axis | Question Type | What It Tests | Weight |
|------|--------------|---------------|--------|
| Storage Breadth | retrieval | Did you store this entity? | 30% |
| Memory Maintenance | update | Did you update the corrected value? | 25% |
| Reasoning | comprehension (20 types) | Can you compute from stored data? | 25% |
| Efficiency | — | Correct answers / budget | 20% |

**Available models** (Chutes platform, sorted by evaluation value):
- `Qwen/Qwen3.5-397B-A17B-TEE` — Strongest open-source, 397B MoE
- `Qwen/Qwen3-235B-A22B-Instruct-2507-TEE`
- `MiniMaxAI/MiniMax-M2.5-TEE` — Third vendor, SWE-bench 80%+
- `moonshotai/Kimi-K2.5-TEE` — Moonshot multimodal
- `zai-org/GLM-5-TEE` — Zhipu flagship

**Real evaluation**: `bench.py --model <name>` or `inspect eval eval_task.py`, using real LLM + real backend.

**Simulation** (`simulation.py`): System self-test, not evaluation. 9 deterministic strategies to verify scoring invariants.

**Memory interface**: OpenClaw compatible (Write/Edit/Read/memory_search). Backends: ChromaDB (vector store) + MarkdownBackend (MEMORY.md file + hybrid search).

## Architecture

Detailed architecture in `docs/ROADMAP.md` §2. Core modules:

- `worlds/` — 10 domain templates (company/research/city/hospital/sport/movie/university/codebase/project/agentteam), each with 21-23 attributes (6 dtypes), 20 reasoning question types + scorers + Inspect AI integration
- `evaluation/` — Answer validation + LLM judge
- `memory/` — Budget management + backends (ChromaDB/MarkdownBackend)
- `agents/stream_agent.py` — Real LLM agent runner
- `simulation.py` — 9-strategy system self-test
- `bench.py` — CLI entry point
- `protocol.py` — Evaluation protocol (tier definitions, scoring functions, JSON schema)
- `training/` — Independent training module (long-term evolution direction)
  - Multi-framework support (verl / slime), multi-approach (SFT / RL)
  - Goals: Ease of use (quick start, auto-tuning, remote training), efficiency (fast convergence, low cost, convenient data collection), self-iteration (CLI visualization, feedback loops, continuous improvement)
- `training/env.py` — MemoryEnv (RL environment) + SFT trajectory generation
- `adapters/` — RL framework adapter layer (verl + slime)

## Dead Ends

| Approach | Why It Failed |
|----------|--------------|
| Fixed question pool + fixed answers | Can be memorized |
| Small entity set (< 100) | Can be enumerated |
| Structured needle | Can be classified and skipped |
| WikiText as filler | Perplexity uncontrollable |
| Different wording to distinguish question types | Wording attack |
| Read everything then answer (pure RAG) | Tests retrieval, not memory management |
| Only ask for maximum values | "Always pick the largest" attack |
| Questions change based on storage | Agent manipulates questions via selective storage |

## Autonomous Development

When running `/loop`, read the corresponding thread file in the `sessions/` directory.

Thread files:
- `sessions/EXECUTOR.md` — Execution thread (write code, run tests, commit)
- `sessions/AUDITOR.md` — Audit thread (dispatch hub — auditing, design, direction decisions)
- `sessions/EVALUATOR.md` — Evaluation thread (run model evaluations, collect data)
- `sessions/TRAINER.md` — Training thread (RL training loop development and verification, independent code push)
- `sessions/WRITER.md` — Paper thread (academic paper writing, independent repo `../memorygym-paper/`)

Information flow:
- Audit thread → Execution thread: Dispatches Phase tasks via the TODO section in EXECUTOR.md
- Audit thread → Evaluation thread: Dispatches evaluation batches via the task queue in EVALUATOR.md
- Audit thread → Paper thread: Provides review feedback and data requests via the feedback section in WRITER.md
- Training thread → Audit thread: Shares experiment findings and design suggestions via the §Strategic Feedback section in TRAINER.md
- Paper thread → Audit thread: Requests supplementary experiments via the §Data Requests section in WRITER.md
- Training thread pushes code to remote independently; audit thread reviews changes after rebase
