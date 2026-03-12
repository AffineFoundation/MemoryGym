#!/usr/bin/env python3
"""Quick rollout smoke test — inference only, fits in ~10GB VRAM.

Validates:
- run_episode works with rollout_max_tokens / turn-level rewards
- New templates (project, agentteam) work
- Shaped rewards are collected per-turn

Usage:
    CUDA_VISIBLE_DEVICES=0 python scripts/smoke_rollout.py \
        --model /path/to/Qwen3-4B \
        --adapter checkpoints/sft-v3-write-edit-read
"""
from __future__ import annotations

import argparse
import inspect
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.grpo_train import run_episode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--templates", nargs="+",
                        default=["company", "project", "agentteam"])
    parser.add_argument("--tier", default="lite")
    parser.add_argument("--rollout-max-tokens", type=int, default=6144)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--load-in-4bit", action="store_true",
                        help="Load model in 4-bit quantization")
    parser.add_argument("--backend", default="chromadb",
                        choices=["chromadb", "markdown"])
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading model: {args.model}", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {"trust_remote_code": True, "device_map": "auto"}
    if args.load_in_4bit:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
        )
        print("  4-bit quantization enabled", flush=True)
    else:
        model_kwargs["dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)

    if args.adapter:
        print(f"Loading adapter: {args.adapter}", flush=True)
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
        if args.load_in_4bit:
            print("  Adapter loaded (no merge — 4-bit mode)", flush=True)
        else:
            model = model.merge_and_unload()
            print("  Merged", flush=True)

    # Detect Qwen3 thinking mode
    chat_kwargs = {}
    sig = inspect.signature(tokenizer.apply_chat_template)
    if "enable_thinking" in sig.parameters:
        chat_kwargs["enable_thinking"] = False

    print(f"\n{'='*60}")
    print(f"Smoke Rollout: {len(args.templates)} templates, "
          f"tier={args.tier}, rollout_max_tokens={args.rollout_max_tokens}")
    print(f"{'='*60}\n", flush=True)

    for tmpl in args.templates:
        t0 = time.time()
        print(f"--- {tmpl} (seed={args.seed}) ---", flush=True)

        messages, reward, stats = run_episode(
            model, tokenizer,
            template=tmpl, tier=args.tier, seed=args.seed,
            max_turns=20, max_new_tokens=1024,
            temperature=0.7, chat_kwargs=chat_kwargs,
            rollout_max_tokens=args.rollout_max_tokens,
            backend_type=args.backend,
        )

        elapsed = time.time() - t0
        tr = stats.get("turn_rewards", [])
        correct = stats.get("correct_count", 0)
        total_q = stats.get("total_questions", 0)
        writes = stats.get("writes_used", 0)

        print(f"  reward={reward:.3f}  correct={correct}/{total_q}  "
              f"writes={writes}  turns={len(tr)}  time={elapsed:.0f}s")
        print(f"  turn_rewards: {[round(r, 2) for r in tr[:10]]}"
              f"{'...' if len(tr) > 10 else ''}")
        shaped_total = sum(tr)
        print(f"  shaped_total={shaped_total:.2f}  "
              f"non_zero_turns={sum(1 for r in tr if r != 0)}/{len(tr)}")
        print(flush=True)

    print("SMOKE ROLLOUT COMPLETE", flush=True)


if __name__ == "__main__":
    main()
