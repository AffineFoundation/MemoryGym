# MemoryGym Status Report

> Version 0.10.19 | 2026-03-12 | Phase 116 complete

## Executive Summary

MemoryGym is the only benchmark that simultaneously tests **budget-constrained storage decisions**, provides **RL training environments**, and **proves anti-gaming robustness** through 9 simulation strategies. 123 real evaluations across 5 models and 8 domains confirm the system produces meaningful, reproducible scores with clear discriminative power.

---

## 1. What Problem Does MemoryGym Solve?

Every existing memory benchmark (LoCoMo, MemoryAgentBench, LongMemEval, AMA-Bench) tests the same thing: **can the agent find information it was given?** This is a retrieval problem, not a memory management problem.

Real-world agents face a fundamentally different challenge. A customer service agent processing 500 tickets per day cannot store everything. A research assistant monitoring 200 papers per week must decide what matters. The critical question is not "can you find it?" but **"did you choose to keep it?"**

MemoryGym is the first system designed to answer this question rigorously:

| Challenge | Real Agent Scenario | MemoryGym Implementation |
|-----------|-------------------|--------------------------|
| Information overload | 500 tickets/day, can't store all | 60 entities, budget of 30 writes |
| Prioritization | Which tickets matter most? | Entity importance weighting, question-weighted sampling |
| Information decay | Ticket status changes over time | Correction events modify entity attributes mid-stream |
| Cross-session persistence | Yesterday's context is gone today | Multi-session evaluation (3 sessions, conversation reset) |
| Noise filtering | Irrelevant emails mixed with real updates | Noise documents mention entity names without useful data |

No other benchmark forces the agent to make **storage trade-offs under hard budget constraints**. This is what makes MemoryGym unique.

---

## 2. System Design

### 2.1 Evaluation Flow

```
seed → WorldTemplate → generate N entities (21-23 attributes each)
                       → render as natural language documents
                       → stream events to agent:
                           ├── INGEST batches (entity documents)
                           ├── CORRECTION events (attribute values change)
                           ├── NOISE documents (entity names, no useful data)
                           ├── SESSION BREAKS (clear conversation, keep memory)
                           └── QUESTIONS (adaptive, based on world state)
                       → agent uses tools: Write / Edit / Read / memory_search
                       → 4-axis scoring against ground truth
```

### 2.2 Four-Axis Scoring

| Axis | Weight | What It Measures | How |
|------|--------|-----------------|-----|
| Breadth | 30% | Storage coverage | Retrieval accuracy on stored entities |
| Maintenance | 25% | Update capability | Correction accuracy × storage coverage gate |
| Reasoning | 25% | Computation on stored data | 20 competency types (aggregation, comparison, multi-hop, etc.) |
| Efficiency | 20% | Budget utilization | Correct answers / write budget |

**Why these weights?** Breadth is highest because storage decisions are the core capability. Maintenance is next because outdated information is worse than no information. Reasoning validates that stored data is usable, not just parked. Efficiency rewards agents that achieve more with fewer writes.

`abstention_diagnostic` is reported separately (not in composite) — it measures whether the agent correctly says "I don't know" for unstored entities.

**Phase 112 — Correction Edit 免预算**: The biggest single-change impact. Correction Edits no longer consume write budget, allowing agents to update stored data after corrections. Impact: composite +3.6pp, maintenance +5.6pp. M>0% rate improved from ~20% to 70%.

### 2.3 Evaluation Tiers

| Tier | Entities | Questions | Corrections | Budget | Pressure Ratio | Sessions |
|------|----------|-----------|-------------|--------|----------------|----------|
| lite | 30 | 10 | 3 | 15 | 2:1 | 1 |
| standard | 60 | 20 | 5 | 30 | 2:1 | 1 |
| hard | 120 | 40 | 10 | 30 | 4:1 | 1 |
| multi | 60 | 20 | 5 | 30 | 2:1 | 3 |

The `hard` tier doubles entities while keeping the same budget — the agent must be twice as selective. The `multi` tier resets conversation context between sessions while preserving the memory backend, testing cross-session persistence.

### 2.4 World Templates

8 domain templates, each with domain-specific characteristics:

| Template | Entities | Attributes | Correction Rate | Question Focus |
|----------|----------|------------|-----------------|----------------|
| company | 600 names | 23 | 10% | Financial reasoning (comprehension=35%) |
| research | 625 names | 21 | 8% | Citation analysis (comprehension=35%) |
| city | 600 names | 23 | 5% | Infrastructure recall (retrieval=45%) |
| hospital | 600 names | 23 | 15% | Status monitoring (update=30%) |
| sport | 600 names | 23 | 12% | Performance tracking (update=25%) |
| movie | 600 names | 23 | 7% | Box office analysis (default weights) |
| university | 600 names | 23 | 10% | Academic performance |
| codebase | 600 names | 23 | 10% | Software metrics |

Each template uses 6 data types: `int`, `float`, `text`, `enum`, `date`, `list_float`. The `list_float` type generates domain-specific temporal patterns (seasonal revenue for companies, citation impact curves for research, exponential box office decay for movies).

### 2.5 Twenty Reasoning Competencies

| Category | Types | Example |
|----------|-------|---------|
| Basic (9) | synthesis, aggregation, cross_category, conditional, ratio, comparison, multi_hop, outlier, delta | "Which Technology company has the highest revenue?" |
| Correction (2) | counterfactual, multi_constraint | "What was the employee count BEFORE the correction?" |
| Relationship (5) | lookup, hop, chain, count, filter | "What is Company A's supplier's revenue?" |
| New dtype (4) | temporal_trend, temporal_extreme, text_match, enum_filter | "Is revenue trending up or down over the last 5 quarters?" |

### 2.6 Memory Interface (OpenClaw Compatible)

Tools: `Write` / `Edit` / `Read` / `memory_search`. Two backends:

- **ChromaDB**: Embedding-based vector search (all-MiniLM-L6-v2)
- **MarkdownBackend**: MEMORY.md file + hybrid search (BM25 70% + vector 30% + RRF fusion)

Backend comparison (batch 14, 4 evals each): MarkdownBackend 30% vs ChromaDB 31.7% — no significant difference. Retrieval bottleneck is model-side, not backend-side.

---

## 3. Anti-Gaming: Why Scores Cannot Be Faked

This is the most critical design property. Every scoring change is validated against 9 deterministic simulation strategies:

### 3.1 Simulation Invariants

```
perfect (store all, update all)        = 100%   ← proves questions are answerable
strategic (store 70%, update)          ≈  65%   ← proves strategy matters
priority_strategic (store important)   >  random ← proves importance weighting works
template_expert (domain-aware)         >  strategic ← proves domain knowledge helps
naive (store 40%, no updates)          ≈  19%   ← proves updates matter
guesser (store nothing, guess)         =   0%   ← proves guessing is impossible
smart_guesser (guess median/midpoint)  <=  5%   ← proves clever guessing fails
abstainer (store all, always "IDK")    <  15%   ← proves blanket abstention has a ceiling
```

### 3.2 Specific Attack Vectors (Verified Dead)

| Attack | Why It Fails |
|--------|-------------|
| Memorize question bank | Each seed generates a completely different world. 600+ name pool × 22 attributes × random seed = effectively infinite combinations |
| Guess median/common values | Integer exact match required. Probability of guessing correctly < 1/1000 per question |
| Store names without values | `detect_stored_entities` requires both entity name AND numeric values to be present |
| Always say "I don't know" | `trick_retrieval` questions have real answers; blanket abstention scores 0 on them |
| Manipulate questions by selective storage | Questions are generated independently of storage decisions |
| Overfit via RL training | `eval_salt` changes numeric values for same seed, preventing memorization across training runs |
| Learn distractor patterns | Distractor templates are direction-neutral (no linguistic markers distinguish correct from incorrect) |
| Game correction detection | Empty search results don't trigger correction reward (Phase 44 fix) |

---

## 4. Empirical Evidence: 123 Real Evaluations

### 4.1 Multi-Model Results (V2, 123 evals, 5 models × 8 templates)

| Model | N | Composite | Avg Score | Templates |
|-------|---|-----------|-----------|-----------|
| Qwen3.5-397B | 71 | **18.0%** | 31.0% | 8/8 |
| Qwen3-235B | 11 | **17.7%** | 20.9% | 8/8 |
| MiniMax-M2.5 | 11 | **15.2%** | 21.8% | 8/8 |
| Kimi-K2.5 | 21 | **15.2%** | 26.0% | 8/8 |
| GLM-5 | 9 | **10.2%** | 20.6% | 8/8 |

### 4.2 What These Numbers Prove

**1. The benchmark discriminates genuine capability differences.**

The score distribution (0% to 48%) spans a wide range with clear ordering:
- **Top**: Qwen3.5-397B (18.0%) and Qwen3-235B (17.7%) — strongest storage + retrieval
- **Mid**: MiniMax-M2.5 and Kimi-K2.5 (both 15.2%) — competitive but weaker on breadth
- **Bottom**: GLM-5 (10.2%) — weakest tool use and storage decisions

**2. Breadth is the cascade bottleneck.**

Breadth averages only 10.8% across all models. Low storage coverage cascades: reasoning and maintenance also fail because the data was never stored. This is the primary target for improvement.

**3. Correction Edit 免预算 is the largest single-change impact.**

Phase 112 made correction Edits free. Impact: composite +3.6pp, maintenance +5.6pp. Before this change, agents exhausted their 30 writes during ingest and could not Edit when corrections arrived. After: M>0% rate improved from ~20% to 70%.

**4. entities_per_write = 1.0 across all models.**

No model packs multiple entities per write operation. This represents a major untapped optimization.

### 4.3 Variance Analysis

Models show high variance (CV ≈ 55-65%). Root cause: template difficulty variation (MEDIUM), seed randomness (MEDIUM), entity name composition (LOW). Best results: Qwen3.5 company seed 9 at 48% composite.

Recommendation: use 5+ seeds per evaluation for stable mean estimates.

---

## 5. RL Training: The Unique Differentiator

No competing benchmark provides an RL training environment.

### 5.1 Training Architecture

```
MemoryEnv (training/env.py)
├── reset() → observation (formatted text, same as real eval)
├── step(action) → (observation, reward, done, info)
├── Reward modes:
│   ├── binary: correct=+1.0, incorrect=0.0
│   └── shaped: store=+0.3, correction_flow=+0.5, answer=+1.0
├── get_verifiable_reward() → accuracy (for GRPO)
├── Correction Edit 免预算 (Phase 112, aligned with eval)
└── Tier support: lite → standard → hard (curriculum)

Training Module (training/)
├── env.py         — MemoryEnv + SFT trajectory generation
├── common.py      — Shared tools (model loading, assistant mask, chat template)
├── cli.py         — Unified CLI (data/sft/grpo/smoke)
└── __main__.py    — python -m memorygym.training entry

Adapters (adapters/)
├── verl_adapter.py — AgentLoopBase integration, token masking
├── verl_reward.py — GRPO compute_score function
└── slime_adapter.py — custom generate/reward interface
```

### 5.2 Training Progress

**SFT v6 data ready**: 160 perfect + 160 strategic trajectories, 8 templates, Edit coverage ≥45%.

**GRPO v3 code ready**: IPS (importance sampling) + DAPO Clip-Higher + KL regularization + clipped ratio. Addresses v2 policy collapse (loss → negative).

**Blocked**: GPU SSH not reachable for 9+ days. Requires infrastructure admin intervention.

---

## 6. Competitive Landscape

### 6.1 Direct Comparison (2025-2026 Benchmarks)

| Capability | MemoryGym | AMemGym (ICLR'26) | MemoryAgentBench (ICLR'26) | LongMemEval (ICLR'25) | AMA-Bench (Feb'26) |
|-----------|-----------|---------|-----------------|------------|-----------|
| Budget-constrained storage | **Yes** | No | No | No | No |
| RL training environment | **Yes (MemoryEnv)** | No | No | No | No |
| Anti-gaming verification | **9 strategies** | No | No | No | No |
| Deterministic reproduction | **Seed-based** | No | No | No | No |
| Multi-session evaluation | Yes (3 sessions) | Yes | No | Yes | No |
| Correction/update testing | Yes (free Edit) | No | Conflict resolution | No | No |
| Domain templates | 8 | Schema-based | Multi-turn tasks | Chat logs | Real trajectories |

### 6.2 Emerging Competitors (2026)

| System | Approach | Relevance |
|--------|----------|-----------|
| mem-agent (Dria/HF) | Markdown file memory + GSPO training | Validates RL for memory; reward shaping >> algorithm |
| Memory-R1 | ADD/UPDATE/DELETE/NOOP + GRPO/PPO | Small-data generalization |
| AgeMem (2601.01885) | Step-wise GRPO + 3-stage curriculum | Addresses sparse reward |
| A-MAC (2603.04549) | 5-factor admission | Fine-grained memory admission |
| PlugMem (Microsoft) | Hierarchical memory architecture | Production memory management |
| BudgetMem (2511.04919) | Dual-tier memory + trainable gating + budget constraints | Closest competitor; token-level vs our entity-level tool-based |
| MEM-alpha (2509.25911) | RL memory construction, 13x generalization | Validates RL training for memory policies |
| MemoryArena | Interdependent multi-session agentic memory | Multi-session competitor |

---

## 7. Engineering Maturity

```
Codebase:     ~13,000 lines of production code
              ~5,000 lines of test code
              437 tests passing
              All files ≤ 1,000 lines

Templates:    8 domains × 600+ entity names × 21-23 attributes × 6 dtypes

Eval data:    123 real evaluations, 5 models, 5 vendors, 8 templates

Backends:     ChromaDB (embedding) + MarkdownBackend (BM25+vector hybrid)

Training:     MemoryEnv (binary + shaped reward)
              verl + slime adapters
              SFT v6: 320 trajectories (160 perfect + 160 strategic)
              GRPO v3 code ready (IPS + DAPO + KL)
              Remote training CLI (scripts/train.py)

Anti-gaming:  9 simulation strategies
              eval_salt prevents training overfit
              437+ invariant checks per validation run
```

### Version History

| Version | Phase | Key Changes |
|---------|-------|-------------|
| 0.1.x | 1-7 | Initial system: company template, basic scoring |
| 0.2.x | 8-17 | 6 templates, 18 reasoning types, Inspect AI |
| 0.3.x | 18-24 | Self-audit, affinetes SDK, RL training |
| 0.4.x | 25-28 | Scoring unification, red team audit |
| 0.5.0 | 29-44 | V2 system: counterfactual questions, template differentiation, noise injection |
| 0.6.x | 45-65 | OpenClaw tools (Write/Edit/Read), MarkdownBackend, mem0 removal, training module restructure |
| 0.7.x-0.9.x | 67-93 | Bug fixes, SFT trajectory quality, RL reward alignment, CLI UX |
| 0.10.x | 94-114 | University/Codebase templates (8 total), Correction Edit free (Phase 112), validators routing, 123 evals |

---

## 8. Honest Assessment

### 8.1 Breadth is the Primary Bottleneck
10.8% breadth across all models. Low storage coverage cascades into reasoning and maintenance failures. This is a model-side limitation, not a system issue.

### 8.2 Training Not Yet Validated End-to-End
SFT v6 data and GRPO v3 code are ready, but GPU access has been blocked for 9+ days. Largest open risk.

### 8.3 Reasoning Tests Computation, Not Understanding
All 20 reasoning types are formula-based. Measures "can you compute on stored data?" not semantic understanding.

### 8.4 Known Resource Leaks
MemoryEnv creates ChromaDB collections per reset without cleanup. Needs fixing for training loops.

---

## 9. Conclusion

MemoryGym answers a question no other benchmark asks: **can an LLM agent make intelligent storage decisions under resource pressure?**

123 real evaluations across 5 models show a 0-48% score range. Current best: **18.0% composite (Qwen3.5-397B, 71 evals)**. The gap between 18% and 100% represents a concrete capability deficit — and MemoryGym is the only system designed to both measure and close it through RL training.
