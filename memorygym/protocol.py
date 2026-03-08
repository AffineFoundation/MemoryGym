"""Standard evaluation protocol: tiers, aggregation, and output schema.

Defines official evaluation configurations for reproducible benchmarking.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

TIERS: dict[str, dict[str, int]] = {
    "lite": {
        "entities": 30,
        "questions": 10,
        "corrections": 3,
        "write_budget": 15,
    },
    "standard": {
        "entities": 60,
        "questions": 20,
        "corrections": 5,
        "write_budget": 30,
    },
    "hard": {
        "entities": 120,
        "questions": 40,
        "corrections": 10,
        "write_budget": 30,
    },
}

OFFICIAL_SEEDS = list(range(10))

OFFICIAL_TEMPLATES = ["company", "research", "city", "hospital", "sport"]

SCHEMA_VERSION = "1.0"

# Composite weights — must sum to 1.0
WEIGHTS = {
    "breadth": 0.30,
    "maintenance": 0.25,
    "reasoning": 0.25,
    "efficiency": 0.20,
}


def _stderr(values: list[float]) -> float:
    """Standard error of the mean."""
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(variance / n)


def aggregate_results(
    per_seed_results: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Aggregate per-seed results into mean ± stderr for each axis.

    Each per_seed_results entry must have keys:
    - breadth, maintenance, reasoning, efficiency, abstention_diagnostic
    - composite (or computed from axes)

    Returns dict with keys: composite, breadth, maintenance, reasoning,
    efficiency, abstention_diagnostic. Each maps to {"mean": ..., "stderr": ...}.
    """
    axes = ["composite", "breadth", "maintenance", "reasoning",
            "efficiency", "abstention_diagnostic"]
    result: dict[str, dict[str, float]] = {}
    for axis in axes:
        values = [r[axis] for r in per_seed_results if axis in r]
        if values:
            result[axis] = {
                "mean": round(sum(values) / len(values), 4),
                "stderr": round(_stderr(values), 4),
            }
        else:
            result[axis] = {"mean": 0.0, "stderr": 0.0}
    return result


def compute_composite(
    breadth: float, maintenance: float, reasoning: float, efficiency: float,
) -> float:
    """Compute composite score from 4 axes."""
    return (WEIGHTS["breadth"] * breadth
            + WEIGHTS["maintenance"] * maintenance
            + WEIGHTS["reasoning"] * reasoning
            + WEIGHTS["efficiency"] * efficiency)


def format_leaderboard_entry(
    model: str,
    tier: str,
    backend: str,
    per_seed_results: list[dict[str, Any]],
    config: dict[str, Any],
    per_template: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Generate standard JSON output for leaderboard submission.

    Args:
        model: Model identifier.
        tier: Evaluation tier (lite/standard/hard).
        backend: Backend type (chromadb/mem0).
        per_seed_results: List of per-seed result dicts with axis scores.
        config: Evaluation configuration dict.
        per_template: Optional per-template grouped results.

    Returns:
        Standard schema dict ready for JSON serialization.
    """
    results = aggregate_results(per_seed_results)

    entry: dict[str, Any] = {
        "memorygym_version": "0.4.0",
        "schema_version": SCHEMA_VERSION,
        "model": model,
        "tier": tier,
        "backend": backend,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "results": results,
    }

    if per_template:
        entry["per_template"] = {
            name: aggregate_results(seeds)
            for name, seeds in per_template.items()
        }

    entry["per_seed"] = per_seed_results

    return entry
