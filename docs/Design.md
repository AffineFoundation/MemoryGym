# MemoryGym (MemoryBench)

**A benchmark for evaluating memory management in LLM agents under resource constraints.**

MemoryGym measures whether an agent can **decide what to store, update outdated information, and reason over limited memory** — a capability largely untested by existing benchmarks. 

---

# Motivation

Most existing LLM memory benchmarks evaluate **retrieval ability**.

Examples:

* LoCoMo
* MemoryAgentBench
* LongMemEval

These benchmarks test whether a model can **find information in long contexts**.

However, real-world agents face a different challenge:

> When an agent sees **hundreds of documents but can only store a small number of memories**, it must decide **what to remember**.

This introduces three critical capabilities:

1. **Selective Storage**
   Decide which information is worth storing.

2. **Memory Maintenance**
   Update or correct stored knowledge when new information arrives.

3. **Reasoning Over Memory**
   Derive answers from incomplete stored fragments.

No existing benchmark evaluates all three simultaneously.

**MemoryGym is the first benchmark designed for this problem.**

---

# Key Features

### Resource-Constrained Memory

Agents operate under a strict **memory write budget**.

Example:

```
30 entities
15 memory slots
```

Agents must decide **which entities to store** and **which to discard**.

---

### Dynamic Memory Updates

Information may change during the task.

Example:

```
Original:
Vortex Labs employees = 5564

Correction event:
Vortex Labs employees = 3870
```

Agents must **detect and update stored memory**.

---

### Implicit Contradictions

Later documents may contain **conflicting values without explicit correction signals**.

Example:

```
Original document:
market_cap = 54,245

Later document:
market_cap = 27,599
```

The agent must identify the contradiction and update its memory.

---

### Multi-Step Reasoning Tasks

MemoryGym includes **14 question types**, covering realistic reasoning patterns.

Examples:

| Type        | Example                                           |
| ----------- | ------------------------------------------------- |
| retrieval   | How many employees does Nexus Digital have?       |
| update      | What is the corrected employee count?             |
| synthesis   | Which technology company has the highest revenue? |
| aggregation | Average profit margin of healthcare companies     |
| multi-hop   | Revenue of the company with the most employees    |
| comparison  | Which company has higher profit margin?           |
| delta       | How much did employees change after correction?   |
| abstention  | Question about unstored entity                    |

---

# Benchmark Structure

Each evaluation run generates a **synthetic world**.

Example entity:

```
Entity: Nexus Digital
Category: Technology

revenue_m: 3847
employees: 12453
market_cap_m: 54245
debt_ratio: 0.73
offices: 28
profit_margin: 0.156
rd_budget_m: 892
founded_year: 1987
```

These entities are rendered into **natural language documents (~250 words each)**.

Agents interact through a sequence of events:

```
INGEST documents
QUESTION
CORRECTION
QUESTION
INGEST (contradiction)
QUESTION
...
```

---

# Domain Templates

MemoryGym currently supports **6 domains**.

| Template | Domain        | Entity              |
| -------- | ------------- | ------------------- |
| company  | business      | companies           |
| research | academia      | research institutes |
| city     | urban         | cities              |
| hospital | healthcare    | hospitals           |
| sport    | sports        | teams               |
| movie    | entertainment | films               |

Each domain includes:

```
600 entity names
10 attributes
10–12 categories
```

This produces **effectively unlimited evaluation worlds**.

---

# Evaluation Metrics

MemoryGym evaluates four dimensions.

| Metric      | Weight | Description               |
| ----------- | ------ | ------------------------- |
| breadth     | 0.25   | retrieval accuracy        |
| maintenance | 0.25   | memory update accuracy    |
| reasoning   | 0.30   | reasoning task accuracy   |
| efficiency  | 0.20   | accuracy per memory write |

Final score:

```
composite = weighted sum of all metrics
```

---

# Example Evaluation Results

| Model        | Parameters | Template | Score |
| ------------ | ---------- | -------- | ----- |
| Qwen3.5-397B | 397B       | hospital | 90%   |
| Qwen3.5-397B | 397B       | research | 70%   |
| Kimi-K2.5    | -          | company  | 50%   |
| Qwen3-32B    | 32B        | company  | 45%   |
| DeepSeek-V3  | 671B       | company  | 37%   |
| GPT-OSS-120B | 120B       | company  | 0%    |

Observations:

* Large performance spread (**0% – 90%**)
* Most models fail **memory maintenance**
* Model size does **not guarantee better memory management**

---

# Anti-Cheating Design

MemoryGym includes multiple anti-cheating mechanisms.

### Dynamic World Generation

Each run uses a different **random seed**:

```
seed → new entities → new documents
```

Memorizing answers is impossible.

---

### Numeric Precision

Values must match **exact numeric answers**, preventing guessing strategies.

---

### Strategy Invariant Tests

Simulated strategies must produce expected scores.

| Strategy          | Expected Score |
| ----------------- | -------------- |
| perfect           | 100%           |
| strategic storage | ~65%           |
| naive storage     | ~19%           |
| guessing          | 0%             |
| abstaining        | ~15%           |

---

# Difficulty Tiers

| Tier     | Entities | Questions | Corrections | Memory Budget |
| -------- | -------- | --------- | ----------- | ------------- |
| lite     | 30       | 10        | 3           | 15            |
| standard | 60       | 20        | 5           | 30            |
| hard     | 120      | 40        | 10          | 30            |

Hard tier introduces **4× information overload under the same memory budget**.

---

# RL Training Support

MemoryGym is designed not only for evaluation but also **RL training**.

Integrated with modern agent RL frameworks:

* Agent-R1
* Search-R1
* VerlTool
* AgentGym-RL

Key training components:

* outcome-based rewards
* multi-turn RL interaction
* curriculum learning
* tool-call masking

---

# Project Status

```
Phase 7 completed
```

Current status:

* 249 tests passing
* 0 TODO / FIXME
* 6 domain templates
* 8 evaluated models
* full trajectory logging
* RL training environment ready

---

# The Core Question

MemoryGym answers a previously untested question:

> Can LLM agents make intelligent memory management decisions under resource constraints?

Current results suggest:

* even the strongest models achieve only **60–90%**
* most models score **near zero on memory maintenance**

This represents a **real capability gap in current LLM agents**.

MemoryGym provides the first benchmark capable of **measuring and training for this capability**.
