# MemoryBench v3 — System Design

## 1. Overview

MemoryBench evaluates LLM agents' **memory management** ability — the capacity to make strategic storage decisions under constraints that maximize future task performance.

**Core loop**: seed → select 2 domains → generate KB per domain → build 25-task stream → agent processes tasks using MCP memory tools → 4-dimensional scoring.

**Key insight**: Write-time is test-time. The challenge is not retrieval quality (which existing benchmarks already measure), but deciding *what* to store, *when* to update, and *what* to discard under budget pressure.

### Tech Stack

| Layer | Choice | Purpose |
|-------|--------|---------|
| Evaluation framework | [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | Task definition, agent loop, scoring |
| Tool protocol | [MCP](https://modelcontextprotocol.io/) | Standardized agent-memory interaction |
| Memory backend | ChromaDB / mem0 | Vector storage for memory entries |
| Simulation | Built-in agents | 5 strategy baselines (perfect, strategic, fixed, naive, guesser) |

## 2. Three-Layer Generation Pipeline

### Layer 1: Knowledge Base (KB)

Given a seeded RNG, deterministically generates structured entities with attributes and relationships.

```
@dataclass
class Entity:
    id: int
    name: str           # Anti-memorization name (NamePool)
    entity_type: str     # Domain-specific
    attributes: dict     # Variable schema per seed
```

**Three domains** (each seed selects 2):

| Domain | Entity Types | Attributes (select 3-5 per seed) |
|--------|-------------|----------------------------------|
| Organization | Person, Department | salary, age, experience, performance, skills, occupation |
| Research | Researcher, Project | citations, h_index, funding, publications, team_size, duration |
| Logistics | Warehouse, Route | capacity, throughput, distance, cost, delivery_time, inventory |

### Layer 2: Document Renderer

KB entities → natural-language documents with embedded facts. Each task presents a document containing key facts plus contextual text.

### Layer 3: Question Generator

KB → formal rules → questions + ground truth. 6 question types:

| Type | Description | GT Source |
|------|-------------|-----------|
| Retrieval | Direct attribute lookup | `kb.entities[id].attributes[attr]` |
| Synthesis | Aggregate/compute across entities | `sum/max/count(...)` |
| Update | Value after correction | `correction.new_value` |
| Conflict | Resolve contradictory information | Latest epoch value |
| Abstention | Ask about non-existent attribute | Correct answer: "I don't have information about that" |
| Cross-domain | Combine data from both domains | Cross-domain computation |

## 3. Streaming Task Architecture

Unlike v1/v2's "read-then-answer" model, v3 uses **streaming**: each task simultaneously presents new information and asks questions. 25 tasks flow in 4 phases:

1. **Domain A establishment** (tasks 1-8): Build knowledge in first domain
2. **Domain A deepening** (tasks 9-14): Updates, corrections, harder questions
3. **Domain B switch** (tasks 15-20): New domain, cross-domain questions begin
4. **Pressure phase** (tasks 21-25): Mixed domains, synthesis, resource exhaustion

## 4. Memory Interface

5 MCP tools exposed via FastMCP:

| Tool | Cost | Description |
|------|------|-------------|
| `memory_store(content, memory_id?)` | 1 write | Store or update entry (max 500 tokens) |
| `memory_search(query, top_k)` | Free | Semantic search |
| `memory_get(memory_id)` | Free | Retrieve single entry by ID |
| `memory_list()` | Free | List all entries |
| `memory_forget(memory_id)` | Free | Delete entry (no budget refund) |

**Budget constraints**: 30 writes, 500 tokens/entry, 100 max entries. With ~40 entities across 2 domains, selectivity is forced.

### No-Fallback Principle

All evaluation logic must be deterministic. Never add fallback/default values to mask errors. If data is missing or computation fails, raise explicitly.

## 5. Evaluation & Scoring

### 4-Dimensional Scoring

```
composite = 0.30 * accuracy + 0.30 * trajectory + 0.25 * efficiency + 0.15 * adaptability
```

| Dimension | What it measures |
|-----------|-----------------|
| **Accuracy** | Correct answers / total questions |
| **Trajectory** | Quality of memory operations (relevant searches, strategic writes) |
| **Efficiency** | Budget utilization — writes used vs. accuracy achieved |
| **Adaptability** | Performance maintenance across domain switches and corrections |

### Answer Validation

4-layer validator chain: NumericValidator → ExactValidator → SetMatchValidator → SubstringValidator. Synthesis/cross-domain answers use format `"EntityName (value)"` requiring both entity and numeric match.

### Process Score

Tracks `searched_before_answering` — whether the agent consulted memory before responding. Reported independently from accuracy.

## 6. Task Registry & Reproducibility

**Task ID format**: `memorybench:v3:{seed}`

Determinism guarantee: same seed → identical KB, documents, questions, and ground truth. Agent behavior and memory backend behavior are intentionally non-deterministic.

**Seed system**: `random.Random(seed)` with optional `eval_salt` perturbation for anti-fingerprinting.

## 7. Inspect AI Integration

| Module | Purpose |
|--------|---------|
| `inspect_task/task.py` | `@task` definition, dataset construction |
| `inspect_task/solver.py` | Session management, document presentation, context clearing |
| `inspect_task/scorer.py` | GT comparison, multi-dimensional scoring |
| `inspect_task/tools.py` | MCP tool bridging |

## 8. Package Structure

```
memorybench/
  domains/          # 3 domain definitions + name pool
    base.py         # Domain ABC
    organization.py
    research.py
    logistics.py
    names.py        # NamePool (504K unique names)
  generation/       # Content generation
    scenario.py     # Scenario orchestration
    task_stream.py  # 25-task stream builder
    questions.py    # Question templates
  memory/           # Memory system
    store.py        # MemoryStore (simulation)
    budget.py       # Budget enforcement
    mcp_server.py   # FastMCP server
  evaluation/       # Scoring
    scorer.py       # 4-dimensional scorer
    validators.py   # Answer validators
    llm_judge.py    # LLM fallback judge
  simulation/       # Strategy baselines
    agents.py       # 5 agent strategies
  inspect_task/     # Inspect AI integration
    task.py / solver.py / scorer.py / tools.py
  cli.py            # CLI entry point
  config.py         # Configuration
```
