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
        "eval_salt": 1,
    },
    "standard": {
        "entities": 60,
        "questions": 20,
        "corrections": 5,
        "write_budget": 30,
        "eval_salt": 1,
    },
    "hard": {
        "entities": 120,
        "questions": 40,
        "corrections": 10,
        "write_budget": 30,
        "eval_salt": 1,
    },
}

OFFICIAL_SEEDS = list(range(10))

OFFICIAL_TEMPLATES = ["company", "research", "city", "hospital", "sport", "movie"]

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


# Comprehension competency types that map to the reasoning axis.
REASONING_COMPETENCIES = [
    "synthesis", "aggregation", "cross_category", "conditional", "ratio",
    "comparison", "multi_hop", "outlier", "delta",
    "relationship_lookup", "relationship_hop", "relationship_chain",
    "relationship_count", "relationship_filter",
    "temporal_trend", "temporal_extreme",
    "text_match", "enum_filter",
]


def compute_axis_scores(
    by_competency: dict[str, list[bool]],
    n_entities: int,
    stored_count: int,
    writes_used: int,
    write_budget: int,
) -> dict[str, float]:
    """Compute 4-axis scores + composite from per-competency results.

    Args:
        by_competency: Maps competency name to list of correct booleans.
        n_entities: Total entities in the world.
        stored_count: Number of entities the agent stored.
        writes_used: Total memory writes used.
        write_budget: Total writes allowed.

    Returns:
        Dict with keys: breadth, maintenance, reasoning, efficiency,
        composite, abstention_diagnostic.
    """
    def _rate(vals: list[bool]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    breadth = _rate(by_competency.get("retrieval", []))

    maintenance_raw = _rate(by_competency.get("update", []))
    storage_coverage = stored_count / n_entities if n_entities else 0.0
    maintenance = maintenance_raw * min(storage_coverage / 0.5, 1.0)

    reasoning_vals: list[bool] = []
    for c in REASONING_COMPETENCIES:
        reasoning_vals.extend(by_competency.get(c, []))
    reasoning = _rate(reasoning_vals)

    correct_total = sum(
        sum(v) for c, v in by_competency.items()
        if c != "abstention"
    )
    # Efficiency = correct answers per unit of budget, capped at 1.0
    efficiency = min(correct_total / write_budget, 1.0) if write_budget > 0 else 0.0

    composite = compute_composite(breadth, maintenance, reasoning, efficiency)
    abstention_diagnostic = _rate(by_competency.get("abstention", []))

    return {
        "breadth": round(breadth, 4),
        "maintenance": round(maintenance, 4),
        "reasoning": round(reasoning, 4),
        "efficiency": round(efficiency, 4),
        "composite": round(composite, 4),
        "abstention_diagnostic": round(abstention_diagnostic, 4),
    }


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


def trajectory_to_conversation(trajectory: list[dict]) -> list[dict[str, Any]]:
    """Convert a trajectory log into a flat conversation list.

    Args:
        trajectory: List of event dicts from stream_agent, each containing
            turns with role/content/tool_calls/tool_results.

    Returns:
        List of message dicts: [{"role": "system"|"user"|"assistant", "content": ...}, ...]
    """
    conversation: list[dict[str, Any]] = []
    for event in trajectory:
        if event.get("type") == "system":
            conversation.append({
                "role": "system",
                "content": event.get("content", ""),
            })
            continue

        # User message for this event
        content = event.get("content", "")
        if content:
            conversation.append({"role": "user", "content": content})

        # Assistant turns
        for turn in event.get("turns", []):
            if turn.get("role") == "assistant" and turn.get("content"):
                conversation.append({
                    "role": "assistant",
                    "content": turn["content"],
                })
            # Tool results as user messages
            for result_text in turn.get("tool_results", []):
                conversation.append({
                    "role": "user",
                    "content": result_text,
                })
    return conversation
