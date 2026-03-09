#!/usr/bin/env python3
"""Generate training prompts JSONL for verl GRPO training.

Each line: {"prompt": [messages], "extra_info": {...}}
The prompt contains the system prompt + first observation.
extra_info carries episode config for MemoryGymAgentLoop.

Usage:
    python scripts/generate_train_data.py --output data/train.jsonl
    python scripts/generate_train_data.py --seeds 100 --templates company research city
    python scripts/generate_train_data.py --tier standard --seeds 50
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from random import Random

from memorygym.adapters._common import get_system_prompt
from memorygym.protocol import TIERS
from memorygym.simulation import TEMPLATES
from memorygym.training import MemoryEnv


def generate_prompts(
    templates: list[str],
    tier: str,
    seeds: int,
    shuffle_seed: int = 42,
) -> list[dict]:
    """Generate training prompts for verl.

    Each prompt sets up a MemoryEnv episode. The agent loop will
    drive the actual interaction during rollout.
    """
    prompts = []
    tc = TIERS[tier]

    for template_name in templates:
        for seed in range(seeds):
            # eval_salt prevents RL from memorizing seed-specific values.
            # Hash of seed ensures deterministic but varied perturbation.
            salt = (seed * 6971 + hash(template_name)) % (2**16)
            # Create env to get the first observation
            env = MemoryEnv(
                template_name=template_name,
                tier=tier,
                seed=seed,
                eval_salt=salt,
            )
            first_obs = env.reset(seed=seed)
            system_prompt = get_system_prompt(env.write_budget)

            prompt = {
                "prompt": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": first_obs},
                ],
                "extra_info": {
                    "template": template_name,
                    "tier": tier,
                    "seed": seed,
                    "eval_salt": salt,
                    "data_source": "memorygym",
                },
            }
            prompts.append(prompt)

    # Shuffle for training diversity
    rng = Random(shuffle_seed)
    rng.shuffle(prompts)
    return prompts


def main():
    parser = argparse.ArgumentParser(
        description="Generate MemoryGym training prompts for verl",
    )
    parser.add_argument(
        "--output", "-o",
        default="data/train.jsonl",
        help="Output JSONL file path",
    )
    parser.add_argument(
        "--templates",
        nargs="+",
        default=list(TEMPLATES.keys()),
        help="Template names to use",
    )
    parser.add_argument(
        "--tier",
        default="lite",
        choices=list(TIERS.keys()),
        help="Evaluation tier (or use --curriculum for progressive tiers)",
    )
    parser.add_argument(
        "--curriculum",
        action="store_true",
        help="Generate curriculum data: 60%% lite + 30%% standard + 10%% hard",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=100,
        help="Number of seeds per template",
    )
    parser.add_argument(
        "--shuffle-seed",
        type=int,
        default=42,
        help="Seed for shuffling",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.curriculum:
        # Curriculum: 60% lite, 30% standard, 10% hard
        # ScalingInter-RL inspired: start easy, progressively harder
        tier_ratios = [("lite", 0.6), ("standard", 0.3), ("hard", 0.1)]
        prompts = []
        for tier, ratio in tier_ratios:
            tier_seeds = max(1, int(args.seeds * ratio))
            prompts.extend(generate_prompts(
                templates=args.templates,
                tier=tier,
                seeds=tier_seeds,
                shuffle_seed=args.shuffle_seed,
            ))
        # Re-shuffle all together
        rng = Random(args.shuffle_seed)
        rng.shuffle(prompts)
        tier_desc = ", ".join(f"{t}={int(r*100)}%" for t, r in tier_ratios)
    else:
        prompts = generate_prompts(
            templates=args.templates,
            tier=args.tier,
            seeds=args.seeds,
            shuffle_seed=args.shuffle_seed,
        )
        tier_desc = args.tier

    with open(output_path, "w") as f:
        for prompt in prompts:
            f.write(json.dumps(prompt, ensure_ascii=False) + "\n")

    print(f"Generated {len(prompts)} prompts → {output_path}")
    print(f"  Templates: {args.templates}")
    print(f"  Tier: {tier_desc}")
    print(f"  Seeds: {args.seeds}")


if __name__ == "__main__":
    main()
