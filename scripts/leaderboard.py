#!/usr/bin/env python3
"""Generate MemoryGym leaderboard from eval results.

Scans eval/ directory and produces a markdown leaderboard table.

Usage:
    python scripts/leaderboard.py
    python scripts/leaderboard.py --format csv
    python scripts/leaderboard.py -o docs/LEADERBOARD.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def _infer_tier(extra: dict) -> str:
    n = extra.get("n_entities", 0)
    if n <= 30:
        return "lite"
    elif n <= 60:
        return "standard"
    else:
        return "hard"


def load_results(eval_dir: str = "eval") -> list[dict]:
    """Load all eval results from directory."""
    results = []
    for f in sorted(os.listdir(eval_dir)):
        if not f.endswith(".json") or "trajectory" in f:
            continue
        path = Path(eval_dir) / f
        data = json.loads(path.read_text())
        if "task_name" not in data:
            continue  # Skip old-format results
        extra = data.get("extra", {})
        error = data.get("error", "")
        if error:
            continue  # Skip failed evals

        results.append({
            "model": extra.get("model", "?"),
            "template": extra.get("template", "?"),
            "seed": extra.get("seed", "?"),
            "tier": _infer_tier(extra),
            "score": data.get("score", 0),
            "n_entities": extra.get("n_entities", 0),
            "n_questions": extra.get("n_questions", 0),
            "write_budget": extra.get("write_budget", 0),
            "writes_used": extra.get("writes_used", 0),
            "stored_entities": extra.get("stored_entities", 0),
            "by_competency": extra.get("by_competency", {}),
            "has_trajectory": Path(
                str(path).replace(".json", "_trajectory.json")
            ).exists(),
        })

    # Infer tier from entity count
    for r in results:
        n = r["n_entities"]
        if n <= 30:
            r["tier"] = "lite"
        elif n <= 60:
            r["tier"] = "standard"
        else:
            r["tier"] = "hard"

    return results


def aggregate_by_model(results: list[dict]) -> list[dict]:
    """Aggregate results per model, computing mean scores."""
    by_model: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    aggregated = []
    for model, runs in sorted(by_model.items()):
        scores = [r["score"] for r in runs]
        avg = sum(scores) / len(scores) if scores else 0

        # Aggregate competency scores
        comp_scores: dict[str, list[float]] = defaultdict(list)
        for r in runs:
            for k, v in r["by_competency"].items():
                comp_scores[k].append(v)
        comp_avg = {
            k: sum(vs) / len(vs) for k, vs in comp_scores.items()
        }

        templates = sorted(set(r["template"] for r in runs))
        seeds = len(runs)

        aggregated.append({
            "model": model,
            "avg_score": avg,
            "n_evals": seeds,
            "templates": templates,
            "retrieval": comp_avg.get("retrieval", 0),
            "update": comp_avg.get("update", 0),
            "abstention": comp_avg.get("abstention", 0),
            "reasoning_types": {
                k: v for k, v in comp_avg.items()
                if k not in ("retrieval", "update", "abstention")
            },
        })

    aggregated.sort(key=lambda x: -x["avg_score"])
    return aggregated


def format_markdown(results: list[dict], aggregated: list[dict]) -> str:
    """Format results as markdown tables."""
    lines = ["# MemoryGym Leaderboard", ""]

    # Aggregated leaderboard
    lines.append("## Overall Rankings")
    lines.append("")
    lines.append("| Rank | Model                                    | Avg Score | Evals | Templates              |")
    lines.append("| ---- | ---------------------------------------- | --------- | ----- | ---------------------- |")
    for i, a in enumerate(aggregated):
        tmpls = ", ".join(a["templates"])
        lines.append(
            f"| {i+1}    | {a['model']:40} | {a['avg_score']*100:6.1f}%   "
            f"| {a['n_evals']:5} | {tmpls:22} |"
        )

    # Detailed per-eval results
    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| Model                                    | Template | Seed | Tier | Score | Retrieval | Update | Traj |")
    lines.append("| ---------------------------------------- | -------- | ---- | ---- | ----- | --------- | ------ | ---- |")

    sorted_results = sorted(results, key=lambda r: (-r["score"], r["model"]))
    for r in sorted_results:
        bc = r["by_competency"]
        ret = f"{bc.get('retrieval', 0)*100:.0f}%"
        upd = f"{bc.get('update', 0)*100:.0f}%"
        traj = "yes" if r["has_trajectory"] else ""
        lines.append(
            f"| {r['model']:40} | {r['template']:8} | {r['seed']:4} "
            f"| {r['tier']:4} | {r['score']*100:4.0f}% | {ret:9} | {upd:6} | {traj:4} |"
        )

    lines.append("")
    lines.append(f"*Generated from {len(results)} evaluations across "
                 f"{len(set(r['model'] for r in results))} models.*")
    return "\n".join(lines)


def format_csv(results: list[dict]) -> str:
    """Format results as CSV."""
    lines = ["model,template,seed,tier,score,retrieval,update,writes_used,stored_entities"]
    for r in sorted(results, key=lambda x: (-x["score"], x["model"])):
        bc = r["by_competency"]
        lines.append(
            f"{r['model']},{r['template']},{r['seed']},{r['tier']},"
            f"{r['score']:.4f},{bc.get('retrieval', 0):.4f},"
            f"{bc.get('update', 0):.4f},{r['writes_used']},{r['stored_entities']}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate MemoryGym leaderboard",
    )
    parser.add_argument(
        "--eval-dir", default="eval",
        help="Directory containing eval result JSONs",
    )
    parser.add_argument(
        "--format", choices=["markdown", "csv"], default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        help="Output file (default: stdout)",
    )
    args = parser.parse_args()

    results = load_results(args.eval_dir)
    if not results:
        print("No valid eval results found.", file=sys.stderr)
        sys.exit(1)

    aggregated = aggregate_by_model(results)

    if args.format == "csv":
        output = format_csv(results)
    else:
        output = format_markdown(results, aggregated)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
        print(f"Leaderboard written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
