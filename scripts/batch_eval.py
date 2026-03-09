#!/usr/bin/env python3
"""Batch evaluation runner for MemoryGym.

Runs evaluations across multiple models × templates × seeds,
automatically skipping combinations that already have results.

Usage:
    python scripts/batch_eval.py
    python scripts/batch_eval.py --models Qwen/Qwen3.5-397B-A17B-TEE moonshotai/Kimi-K2.5-TEE
    python scripts/batch_eval.py --templates company hospital --seeds 3
    python scripts/batch_eval.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_MODELS = [
    "Qwen/Qwen3.5-397B-A17B-TEE",
    "moonshotai/Kimi-K2.5-TEE",
    "MiniMaxAI/MiniMax-M2.5-TEE",
]

DEFAULT_TEMPLATES = ["company", "research", "city", "hospital", "sport"]


def find_existing(eval_dir: str = "eval") -> set[tuple[str, str, int]]:
    """Find (model, template, seed) combos that already have results."""
    existing = set()
    if not os.path.isdir(eval_dir):
        return existing

    for f in os.listdir(eval_dir):
        if not f.endswith(".json") or "trajectory" in f:
            continue
        path = Path(eval_dir) / f
        try:
            data = json.loads(path.read_text())
            extra = data.get("extra", {})
            # Skip failed evals (allow re-running them)
            if data.get("error"):
                continue
            model = extra.get("model", "")
            template = extra.get("template", "")
            seed = extra.get("seed", -1)
            if model and template and seed >= 0:
                existing.add((model, template, seed))
        except (json.JSONDecodeError, KeyError):
            continue

    return existing


def main():
    parser = argparse.ArgumentParser(
        description="Batch MemoryGym evaluations",
    )
    parser.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS,
        help="Models to evaluate",
    )
    parser.add_argument(
        "--templates", nargs="+", default=DEFAULT_TEMPLATES,
        help="Templates to evaluate",
    )
    parser.add_argument(
        "--seeds", type=int, default=3,
        help="Number of seeds (0..N-1)",
    )
    parser.add_argument(
        "--tier", default="lite",
        choices=["lite", "standard", "hard"],
        help="Evaluation tier",
    )
    parser.add_argument(
        "--eval-dir", default="eval",
        help="Directory for eval results",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be run without executing",
    )
    parser.add_argument(
        "--api-base", default="https://llm.chutes.ai/v1",
        help="API base URL",
    )
    args = parser.parse_args()

    existing = find_existing(args.eval_dir)
    print(f"Found {len(existing)} existing successful evaluations\n")

    # Build task list
    tasks = []
    for model in args.models:
        for template in args.templates:
            for seed in range(args.seeds):
                if (model, template, seed) in existing:
                    continue
                tasks.append((model, template, seed))

    if not tasks:
        print("All evaluations already complete!")
        return

    print(f"Planned: {len(tasks)} evaluations")
    print(f"Models: {', '.join(args.models)}")
    print(f"Templates: {', '.join(args.templates)}")
    print(f"Seeds: 0-{args.seeds - 1}")
    print(f"Tier: {args.tier}")
    print()

    for i, (model, template, seed) in enumerate(tasks):
        print(f"  [{i+1}/{len(tasks)}] {model} / {template} / seed={seed}")

    if args.dry_run:
        print("\n(dry run — no evaluations executed)")
        return

    print()

    # Execute
    successes = 0
    failures = 0
    for i, (model, template, seed) in enumerate(tasks):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(tasks)}] {model} / {template} / seed={seed}")
        print(f"{'='*60}")

        cmd = [
            sys.executable, "-m", "memorygym.bench",
            "--model", model,
            "--template", template,
            "--seed", str(seed),
            "--tier", args.tier,
            "--api-base", args.api_base,
        ]

        try:
            result = subprocess.run(
                cmd, timeout=1800,  # 30 min per eval
                capture_output=False,
            )
            if result.returncode == 0:
                successes += 1
            else:
                failures += 1
                print(f"  FAILED (exit code {result.returncode})")
        except subprocess.TimeoutExpired:
            failures += 1
            print(f"  TIMEOUT (30 min)")
        except KeyboardInterrupt:
            print(f"\n\nInterrupted. Completed {successes}/{i+1} evaluations.")
            sys.exit(1)

    print(f"\n{'='*60}")
    print(f"Batch complete: {successes} succeeded, {failures} failed "
          f"out of {len(tasks)} planned")


if __name__ == "__main__":
    main()
