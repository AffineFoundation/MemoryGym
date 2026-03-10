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

- **Anti-cheating**: 8 simulation strategies verify that no shortcut beats genuine memory management
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

### Available options

```
--model MODEL        LLM model name (OpenAI-compatible)
--seed N             Single seed
--seeds N            Number of seeds (default: 10)
--template T         Template: company, research, city, hospital, sport, movie
--tier TIER          Evaluation tier: lite (default), standard, hard
--backend BACKEND    Memory backend: chromadb (default)
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

6 domain templates generate diverse evaluation scenarios:

- **company**: Tech companies with revenue, employees, R&D spending
- **research**: Research labs with publications, citations, funding
- **city**: Cities with population, GDP, infrastructure
- **hospital**: Hospitals with beds, staff, patient outcomes
- **sport**: Sports teams with wins, scores, player stats
- **movie**: Films with box office, ratings, cast

## Leaderboard

See [LEADERBOARD.md](LEADERBOARD.md) for current results.

Top models (lite tier, averaged across templates):

| Model | Avg Score | Templates |
|-------|-----------|-----------|
| Qwen3.5-397B | 73% | 3 |
| Kimi-K2.5 | 39% | 6 |
| MiniMax-M2.5 | 27% | 5 |

## Architecture

```
memorygym/
├── worlds/          # 6 domain templates + scorer + Inspect AI integration
├── evaluation/      # Answer validation + LLM judge
├── memory/          # Budget management + backends (ChromaDB)
├── agents/          # Real LLM agent runner
├── adapters/        # RL framework adapters (verl/slime)
├── bench.py         # CLI entry point
├── simulation.py    # 8-strategy system self-test
├── training.py      # SFT trajectory generation + MemoryEnv
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
