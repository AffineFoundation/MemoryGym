# MemoryGym

A benchmark for evaluating LLM memory management capabilities. Tests whether agents can selectively store, update, and reason over information under budget constraints.

## What it measures

MemoryGym evaluates 4 axes of memory management:

| Axis | Weight | What it tests |
|------|--------|---------------|
| Storage Breadth | 30% | Can the agent selectively store important entities? |
| Memory Maintenance | 25% | Can the agent update memories when corrections arrive? |
| Reasoning | 25% | Can the agent compute answers from stored data? |
| Efficiency | 20% | How well does the agent use its write budget? |

The agent receives a stream of entity documents (far more than its write budget allows), correction notices that change previously stored data, and questions that test recall and reasoning. An abstention diagnostic (reported separately) measures whether the agent knows what it doesn't know.

## Key properties

- **Anti-cheating**: 9 simulation strategies verify that no shortcut beats genuine memory management
- **Deterministic**: Same seed produces identical scenarios and scores
- **Realistic**: Information overload + limited budget + stale data updates
- **Trainable**: Includes RL environment (MemoryEnv) for training agents

## Installation

```bash
pip install -e .

# With affinetes (containerized eval):
pip install -e ".[affinetes]"
```

## Quick start

### Simulation (system self-test, no LLM needed)

```bash
# Run with invariant checks
python -m memorygym.bench --seeds 10 --validate

# Verbose per-question output
python -m memorygym.bench --seed 0 -v
```

### Real evaluation (requires API key)

```bash
export CHUTES_API_KEY="your-key"

# Single evaluation
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 42 --template company

# Standard tier (60 entities, 20 questions)
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --seed 0 --tier standard

# Official protocol (seeds 0-9, all templates)
python -m memorygym.bench --model moonshotai/Kimi-K2.5-TEE --official -o results.json
```

### Training data generation

```bash
python -m memorygym.training data --seeds 5 --templates company  # Generate SFT trajectories
python -m memorygym.training sft --data data/sft_v6_mixed.jsonl   # Fine-tune (requires torch)
```

### Available options

```
--model MODEL        LLM model name (OpenAI-compatible)
--seed N             Single seed
--seeds N            Number of seeds (default: 10)
--template T         Template: company, research, city, hospital, sport, movie, university, codebase, project, agentteam
--tier TIER          Evaluation tier: lite, standard (default), hard, multi
--backend BACKEND    Memory backend: chromadb (default), markdown
--validate           Run invariant checks
--official           Official mode: seeds 0-9, all templates
```

## Evaluation tiers

| Tier | Entities | Questions | Corrections | Budget | Pressure |
|------|----------|-----------|-------------|--------|----------|
| lite | 30 | 10 | 3 | 15 | 2:1 |
| standard | 60 | 20 | 5 | 30 | 2:1 |
| hard | 120 | 40 | 10 | 30 | 4:1 |

## World templates

10 domain templates generate diverse evaluation scenarios:

- **company**: Tech companies with revenue, employees, R&D spending
- **research**: Research labs with publications, citations, funding
- **city**: Cities with population, GDP, infrastructure
- **hospital**: Hospitals with beds, staff, patient outcomes
- **sport**: Sports teams with wins, scores, player stats
- **movie**: Films with box office, ratings, cast
- **university**: Higher education institutions with enrollment, acceptance rates, research output
- **codebase**: Software modules/services with LOC, contributors, deployment frequency
- **project**: Software projects with budgets, sprints, velocity, risk scores
- **agentteam**: Autonomous agents with throughput, latency, coordination, error patterns

## Leaderboard

See [LEADERBOARD.md](LEADERBOARD.md) for current results.

Top models (averaged across 10 templates and seeds, 150 evals):

| Model | Composite | Evals |
|-------|-----------|-------|
| Qwen3-235B | 18.6% | 18 |
| Qwen3.5-397B | 18.2% | 75 |
| MiniMax-M2.5 | 17.6% | 19 |
| Kimi-K2.5 | 15.8% | 23 |
| GLM-5 | 11.6% | 15 |

## Architecture

```
memorygym/
├── worlds/          # 10 domain templates + scorer + Inspect AI integration
├── evaluation/      # Answer validation + LLM judge
├── memory/          # Budget management + backends (ChromaDB, Markdown)
├── agents/          # Real LLM agent runner
├── adapters/        # RL framework adapters (verl/slime)
├── bench.py         # CLI entry point
├── simulation.py    # 9-strategy system self-test
├── training/        # SFT trajectory generation + MemoryEnv
├── env.py           # OpenEnv (affinetes) interface
└── protocol.py      # Tiers, weights, aggregation
```

## Development

```bash
# Run tests
python -m pytest tests/ -q

# World template tests (fast iteration)
python tests/test_worlds.py

# Simulation invariant checks
python -m memorygym.bench --seeds 10 --validate

# Generate leaderboard
python scripts/leaderboard.py > LEADERBOARD.md
```
