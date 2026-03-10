#!/usr/bin/env python3
"""Generate SFT trajectory data for tool-calling fine-tuning.

Each line: {"messages": [...]} — complete conversation with tool calls.
Uses simulation strategies (perfect/strategic) as expert demonstrations.

Usage:
    python scripts/generate_sft_data.py --output data/sft_train.jsonl
    python scripts/generate_sft_data.py --strategy strategic --seeds 50
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from memorygym.simulation import TEMPLATES
from memorygym.training import generate_sft_trajectory


def main():
    parser = argparse.ArgumentParser(
        description="Generate SFT trajectory data for MemoryGym")
    parser.add_argument(
        "--output", "-o", default="data/sft_train.jsonl",
        help="Output JSONL file")
    parser.add_argument(
        "--templates", nargs="+", default=list(TEMPLATES.keys()),
        help="Templates to use")
    parser.add_argument(
        "--strategy", default="perfect",
        choices=["perfect", "strategic"],
        help="Simulation strategy for expert demonstrations")
    parser.add_argument(
        "--seeds", type=int, default=20,
        help="Seeds per template")
    parser.add_argument(
        "--n-entities", type=int, default=30,
        help="Entities per scenario (lite=30)")
    parser.add_argument(
        "--n-questions", type=int, default=10,
        help="Questions per scenario (lite=10)")
    parser.add_argument(
        "--n-corrections", type=int, default=3,
        help="Corrections per scenario (lite=3)")
    parser.add_argument(
        "--write-budget", type=int, default=15,
        help="Write budget (lite=15)")
    parser.add_argument(
        "--shuffle-seed", type=int, default=42,
        help="Shuffle seed")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    trajectories = []
    for tmpl in args.templates:
        for seed in range(args.seeds):
            messages = generate_sft_trajectory(
                tmpl, seed,
                strategy=args.strategy,
                n_entities=args.n_entities,
                n_questions=args.n_questions,
                n_corrections=args.n_corrections,
                write_budget=args.write_budget,
            )
            trajectories.append({"messages": messages})

    # Shuffle
    rng = Random(args.shuffle_seed)
    rng.shuffle(trajectories)

    with open(output_path, "w") as f:
        for t in trajectories:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    # Stats
    total_msgs = sum(len(t["messages"]) for t in trajectories)
    avg_msgs = total_msgs / len(trajectories)
    print(f"Generated {len(trajectories)} trajectories → {output_path}")
    print(f"  Templates: {args.templates}")
    print(f"  Strategy: {args.strategy}")
    print(f"  Seeds: {args.seeds}")
    print(f"  Avg messages/trajectory: {avg_msgs:.0f}")
    print(f"  Total messages: {total_msgs}")


if __name__ == "__main__":
    main()
