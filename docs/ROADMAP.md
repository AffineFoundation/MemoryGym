# MemoryGym Roadmap

> Authoritative document for project status, evidence, priorities, architecture, and technical decisions.
> Maintained by the autonomous evolution protocol.

**Last updated**: 2026-03-12

---

## 0. Current Status

> New sessions: start here + `sessions/EXECUTOR.md`. Read recent devlog files if more context is needed.

**Current focus**: RL training loop (SFT v6 ready, GRPO v3 code ready, awaiting trainer execution)

**Biggest gap**: Breadth 10.8% is the cascade bottleneck on the eval side; RL training has not yet produced a model exceeding the baseline.

**Completed**:
- Phase 0-28: Core system, template enhancements, scoring unification, red-team audits ✅
- Phase 29-33: V2 system redesign — counterfactual/multi-constraint question types, template event stream differentiation, entity importance, noise injection ✅
- Phase 34-46: Long-context mode, multi-session evaluation, RL shaped reward, version tracking ✅
- Phase 47-50: ChromaDB search precision, mem0 integration, Inspect AI, adapter refinement ✅
- Phase 51: MemoryEnv process-based reward enhancement ✅
- Phase 57-58: System prompt neutralization + mem0 backend removal ✅
- Phase 59-61: Tool interface OpenClaw-ification (Write/Edit/Read) + bug fixes ✅
- Phase 62: MarkdownBackend integration with bench.py + training env ✅
- Phase 63-65: training/env.py alignment with eval + eval_task.py sync + Edit fix ✅
- Phase 67-76: Resource leak, RNG alignment, temporal decay, Edit fallback, event format, simulation validation, version bug, system prompt, Inspect AI path, 3-path consistency tests ✅
- Phase 77-86: Contradiction fix, reasoning type full coverage, data quality, training infra, MarkdownBackend recall, Inspect AI tool names, eval_task.py defaults, test_path_consistency ✅
- Phase 87-93: SFT consecutive message merging, budget overrun fix, question wording leak fix, RL reward aligned with 4-axis scoring, CLI UX fixes ✅
- Phase 94: Dead code cleanup ✅
- Phase 96-101: University/Codebase templates (6→8 templates), constraint fixes ✅
- Phase 102-104: Correction tracking false-positive fix, SFT trajectory fix, Edit coverage improvement ✅
- Phase 106-109: Validator dispatch completion, doc sync, CLI UX polish, LEADERBOARD 4-axis ✅
- Phase 110-114: Validator reasoning type routing, context overflow abstain, **Correction Edit budget-free (Phase 112, highest-impact change)**, stdout scoring consistency, README sync ✅
- 8 templates × 21-23 attrs × 6 dtypes × 20 reasoning competencies
- 437 tests, 9 simulation strategies ALL PASS (v0.10.18)
- 123 real evaluations, 5 models — Qwen3.5=18.0%, Qwen3-235B=17.7%, MiniMax=15.2%, Kimi=15.2%, GLM-5=10.2% (Composite)
- 2 backends: ChromaDB (embedding) + MarkdownBackend (BM25 + vector hybrid search)
- Phase 112 impact: composite +3.6pp, maintenance +5.6pp (16 post-112 evals, M>0% from ~20% to 70%)
- SFT v6 data ready: 160 perfect + 160 strategic trajectories
- GRPO v3 code ready (IPS + DAPO Clip-Higher + KL + clipped ratio)

---

## 1. Project Positioning

MemoryGym is an evaluation and training platform for LLM agent **memory management** — measuring the quality of storage decisions under write-budget pressure.

| Dimension | MemoryGym | Existing Approaches |
|-----------|-----------|---------------------|
| **What it tests** | Storage decisions (what to store, update, discard) | Retrieval quality (LoCoMo), multi-turn memory (MemoryAgentBench) |
| **Budget pressure** | Write count is limited; selective storage required | No budget limits |
| **Memory maintenance** | Tests whether corrections are applied to stored memory | Not tested |
| **Training support** | MemoryEnv (RL environment) + SFT trajectories | Evaluation only |
| **Interface compatibility** | Write/Edit/Read + memory_search (OpenClaw compatible) | Custom interfaces |

---

## 2. Architecture

### 2.1 System Structure

```
memorygym/
├── worlds/                     # World generation system
│   ├── base.py                 # WorldTemplate ABC, World, EntitySpec, Relationship, question generation
│   ├── company/research/city/hospital/sport/movie/university/codebase.py  # 8 domain templates
│   ├── eval_task.py            # Inspect AI task: stream solver
│   └── eval_scorer.py          # 4-axis scorer
├── evaluation/
│   ├── validators.py           # Answer matching (exact → numeric → synthesis → abstention)
│   ├── llm_judge.py            # Multi-model LLM judge
│   └── backend_bench.py        # Backend ceiling test
├── memory/
│   ├── budget.py               # MemoryBudget (write limit)
│   └── backends/               # chromadb + markdown (BM25 + vector hybrid search)
├── agents/
│   ├── stream_agent.py         # Real LLM agent runner
│   └── _tool_helpers.py        # Tool execution logic (Write/Edit/Read/memory_search)
├── simulation.py               # System self-test (9 strategies validate scoring effectiveness)
├── bench.py                    # CLI: real evaluation + simulation
├── protocol.py                 # Standard evaluation protocol (tier definitions, JSON schema)
├── training/                   # SFT trajectory generation + MemoryEnv (RL environment)
│   ├── env.py                  # MemoryEnv + SFT trajectory generation
│   ├── common.py               # Shared utilities (model loading, assistant mask, chat template)
│   ├── cli.py                  # Unified CLI (data/sft/grpo/smoke)
│   └── __main__.py             # python -m memorygym.training entry point
├── adapters/                   # RL framework adaptation layer
│   ├── _common.py              # Shared tool parsing + episode runner
│   ├── verl_adapter.py         # verl AgentLoopBase integration (@register memorygym_agent)
│   ├── verl_reward.py          # verl compute_score reward function
│   └── slime_adapter.py        # slime custom generate/reward
└── scripts/                    # Training scripts
    ├── train.py                # Unified remote training entry (SSH remote + GPU detection + log parsing)
    ├── generate_train_data.py  # Generate training prompts JSONL
    ├── verl_memorygym.yaml     # verl GRPO training config
    └── memorygym_agent.yaml    # agent loop config
```

### 2.2 Scoring System (4 axes)

| Axis | Weight | What It Measures |
|------|--------|------------------|
| breadth | 0.30 | Storage coverage (retrieval accuracy) |
| maintenance | 0.25 | Memory maintenance (update accuracy × coverage gate) |
| reasoning | 0.25 | Reasoning ability (20 competency types: 9 basic + 2 correction + 5 relationship + 4 new dtype) |
| efficiency | 0.20 | Efficiency (correct_count / write_budget) |

abstention_diagnostic is reported separately, not included in composite.

### 2.3 Evaluation Tiers

| Tier | Entities | Questions | Corrections | Budget | Pressure Ratio |
|------|----------|-----------|-------------|--------|----------------|
| lite | 30 | 10 | 3 | 15 | 2:1 |
| standard | 60 | 20 | 5 | 30 | 2:1 |
| hard | 120 | 40 | 10 | 30 | 4:1 |
| multi | 60 | 20 | 5 | 30 | 2:1 (3 sessions) |

### 2.4 Simulation Strategies and Invariants

9 strategies validate scoring effectiveness: perfect=100%, guesser=0%, strategic>naive+10%, abstainer<15%, smart_guesser<=5%.

### 2.5 MemoryEnv (RL Environment)

| Property | Status |
|----------|--------|
| Interface | reset() → str, step(action_text) → (str, float, bool, dict) |
| Tier support | lite/standard/hard |
| Observation | Formatted text (consistent with stream_agent), includes budget context |
| Reward | binary (correct=+1, wrong=0) + shaped (store=+0.3, correction=+0.5, answer=+1.0) |
| get_verifiable_reward() | accuracy, for GRPO use |
| Search | ChromaDB/MarkdownBackend (consistent with real eval) |
| Tool interface | Write/Edit/Read/memory_search (OpenClaw compatible) |
| Correction Edit | Budget-free (Phase 112), consistent with eval |

### 2.6 Reasoning Question Types (20 types)

Basic: synthesis, aggregation, cross_category, conditional, ratio, comparison, multi_hop, outlier, delta
Correction-dependent: counterfactual, multi_constraint
Relationship: relationship_lookup, relationship_hop, relationship_chain, relationship_count, relationship_filter
New dtype: temporal_trend, temporal_extreme, text_match, enum_filter

### 2.7 Test Coverage

437 tests, 9 simulation strategies ALL PASS (v0.10.18)

---

## 3. Evidence

### 3.1 Evaluation Data (v2 — Phase 16+ Enhanced Templates)

> v1 data (10-attribute templates) archived to `eval/archive_v1/`. Below is v2 data (21-23 attributes, 6 dtypes, 20 reasoning types).
> 8 templates: company, research, city, hospital, sport, movie, university, codebase

**123 real evaluations, 5 models, 5 vendors. Full 5-model × 8-template coverage achieved.**

#### Model Rankings (Composite, 123 evals)

| Model | N | Composite | Avg Score | Template Coverage |
|-------|---|-----------|-----------|-------------------|
| Qwen3.5-397B | 71 | **18.0%** | 31.0% | 8/8 |
| Qwen3-235B | 11 | **17.7%** | 20.9% | 8/8 |
| MiniMax-M2.5 | 11 | **15.2%** | 21.8% | 8/8 |
| Kimi-K2.5 | 21 | **15.2%** | 26.0% | 8/8 |
| GLM-5 | 9 | **10.2%** | 20.6% | 8/8 |

#### Phase 112 Impact (Correction Edit Budget-Free)

Phase 112 is the highest-impact change in project history:
- Composite +3.6pp (16 post-112 evals vs pre-112 baseline)
- Maintenance +5.6pp (M>0% from ~20% to 70%)
- Root cause: agents exhaust 30 writes before correction events, unable to Edit → budget-free Edit enables normal updates

#### Key Findings

- **Breadth 10.8% is the cascade bottleneck**: Low storage coverage → reasoning/maintenance also fail due to missing data
- entities_per_write = 1.0 (all models) — multi-entity packing is an unexploited optimization
- Backend comparison: MarkdownBackend 30% vs ChromaDB 31.7% — no significant difference, bottleneck is model-side

### 3.2 v1 Historical Data Summary [archived]

v1 key findings (reference only, scores not comparable with v2):
- Qwen3.5-397B strongest (73% avg), breadth/abstention 100%
- Kimi-K2.5 moderate (40% avg), maintenance weak (mostly 0%)
- v2 scores significantly lower than v1 (22-23 attributes vs 10, higher information density)

### 3.3 Data Index

```
eval/archive_v1/  # v1 data (pre-Phase 16, 10-attribute templates)
├── 49 JSON files (results + trajectories)
└── README.md

eval/              # v2 data (post-Phase 16, 21-23 attribute templates)
├── 130+ JSON files (results + trajectories, 123 valid)
└── 5 models × 8 templates × multiple seeds/tiers
```

---

## 4. Priorities

> Derived from §3 evidence. Directions may change; changes must be documented with rationale.

### Current Priorities

**1. RL Training Loop** — Highest priority
- SFT v6 data ready: 320 mixed trajectories (160 perfect + 160 strategic), 8 templates
- GRPO v3 code ready: IPS + DAPO Clip-Higher + KL regularization + clipped ratio
- Frontier references: MEM-alpha (RL memory construction, 13x generalization), INTENT (budget-aware planning), WebAgent-R1 (binary reward 5-6x improvement)
- Success criteria: 7B model composite ≥ 45%, maintenance ≥ 30%

**2. Evaluation Data Accumulation** — 123 evals reached, full 5-model × 8-template coverage
- Data accumulation largely complete, focus shifting to RL training
- New evals only for regression validation after code changes

**3. Code Quality** — Low priority
- Executor task queue is empty

### Completed Priorities

- ✅ Multi-template eval data (cross-template validity confirmed, 8-template full coverage)
- ✅ Cross-model tool compatibility (5 vendors all non-zero scores)
- ✅ Task complexity upgrades + new world templates (20 reasoning types, 8 templates)
- ✅ V2 system upgrade (Phase 29-44)
- ✅ Tool interface OpenClaw-ification (Phase 59-61)
- ✅ MarkdownBackend development and comparison validation (Phase 62-65)
- ✅ Correction Edit budget-free (Phase 112, +3.6pp composite)

### Priority Change Log

| Date | Change | Rationale |
|------|--------|-----------|
| 2026-03-08 | Initial priority setting | Based on existing eval data analysis |
| 2026-03-08 | Task complexity upgrade raised from #4 to #3 | User instruction |
| 2026-03-08 | Phase 1-3 complete, RL training loop raised to highest priority | Eval system stable |
| 2026-03-09 | V2 system-level redesign | Strategic audit confirmed reasoning mechanization + template strategy homogenization |
| 2026-03-11 | RL training + code quality in parallel | 50 evals stable, backend comparison complete, code audit found resource leak |
| 2026-03-12 | Eval data changed from "in progress" to "largely complete" | 123 evals, 5×8 full coverage |

---

## 5. Technical Decisions

### Confirmed

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Evaluation path | WorldTemplate | Controllable, extensible, deterministic |
| Scoring system | 4-axis + abstention diagnostic | Interpretable, analyzable |
| Numeric validation | Integer exact + float 2% tolerance | Prevents guessing, tolerates display differences |
| Budget context | Dynamic injection (not hard limit) | Storage decisions should be made by the agent |
| MemoryEnv observation | Text format | Consistent with LLM input format |
| RL framework | verl + slime dual adaptation (memorygym/adapters/) | Shared MemoryEnv, thin adaptation layer |
| Multi-entity packing | Allowed (legitimate strategy) | Smart compression is a core skill |
| Efficiency formula | correct_count / write_budget | Does not penalize fewer writes, rewards correct answers |
| Tool interface | Write/Edit/Read/memory_search (OpenClaw compatible) | Standardization |
| Backend | ChromaDB + MarkdownBackend in parallel | Comparison validation showed no significant difference |
| Correction Edit budget-free | Implemented in Phase 112 | Agents exhaust budget before corrections; inability to Edit was root cause of M=0% |

### Pending

| Decision | Options | Decision Timing |
|----------|---------|-----------------|
| GRPO v3 algorithm | KL regularization vs GSPO vs step-wise GRPO | After GPU training experiments |

### Rejected

| Approach | Reason |
|----------|--------|
| Per-batch budget cap | Violates agent autonomous decision principle |
| Custom GRPO implementation | Not a core contribution |
| mem0 backend | Removed in Phase 58 — unstable API, unreliable integration |

---

## 6. Known Issues

| Issue | Severity | Notes |
|-------|----------|-------|
| entities_per_write = 1.0 | Low | Model capability issue, not a system bug. One of the RL training targets |
| ~~MemoryEnv ChromaDB resource leak~~ | ~~Medium~~ | ✅ reset() calls close() → delete_collection() |
| ~~GRPO v2 policy collapse~~ | ~~High~~ | ✅ v3 adds KL regularization + DAPO clip-higher, awaiting GPU validation |
| ~~MarkdownBackend temp directory leak~~ | ~~Low~~ | ✅ Fixed in Phase 79 with close() |
| ~~sport priority>random occasional flaky~~ | ~~Low~~ | ✅ Changed to global avg soft check |
| ~~MemoryEnv search is substring~~ | ~~Medium~~ | ✅ Changed to ChromaDB embedding search |
| ~~stream_agent tool parsing fragile~~ | ~~Medium~~ | ✅ Supports 4 formats |
| ~~Maintenance 0% across the board~~ | ~~High~~ | ✅ Phase 112 Correction Edit budget-free, M>0% from ~20% to 70% |

---

## 7. References

### Agent Memory
- A-Mem (2502.12110), AgeMem (2601.01885), A-MAC (2603.04549)
- Learn to Memorize (2508.16629), MemGPT/Letta (2310.08560)
- mem-agent (Dria/HF — Markdown file + GSPO), Memory-R1 (ADD/UPDATE/DELETE + GRPO)
- PlugMem (Microsoft — hierarchical memory), Memex(RL) (2507.08115)
- MEM-alpha (2509.25911 — RL memory construction, 13x length generalization)
- FluxMem (2602.14038 — adaptive memory structure selection)

### Agent RL Training
- DeepSeek-R1 (2501.12948), Agent-R1 (2511.14460), WebAgent-R1 (2505.16421)
- REDSearcher (2602.14234), Simia (2511.01824)
- Search-R1 (2503.09516), VerlTool (2509.01055), AgentGym-RL (ICLR 2026)
- GSPO (2507.18071 — Qwen3 team, sequence-level importance ratio)
- SELAUR (2602.21158 — uncertainty-aware shaped rewards)
- Training-Free GRPO (2510.08191 — zero-cost semantic advantage distillation)
- Dr.MAS (2602.08847 — per-agent advantage normalization)
- INTENT (2602.11541 — budget-constrained intention-aware tool planning)

### Benchmarks
- LoCoMo (2402.17753), MemoryAgentBench (2507.05257, ICLR 2026), LongMemEval (2024)
- AMemGym (ICLR 2026), openclaw-memory-bench (OpenClaw team)
- PinchBench, GAIA (2311.12983), AgentBench (ICLR 2024)
- BudgetMem (2511.04919 — dual-tier memory + budget constraints)
- StructMemEval (2602.11243 — memory organization structure)
- LoCoMo-Plus (2602.10715 — cognitive memory evaluation)
- Evo-Memory (2511.20857 — self-evolving memory, DeepMind)
- MemoryArena (interdependent multi-session agentic memory)
