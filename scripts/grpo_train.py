#!/usr/bin/env python3
"""GRPO training for MemoryGym: teach tool-calling strategy via RL.

After SFT teaches the model to produce tool calls, GRPO teaches *when*
to search and *how* to use search results to answer questions.

Algorithm:
1. Rollout: run G episodes per scenario, collect (messages, reward)
2. GRPO advantages: (reward - group_mean) / (group_std + eps)
3. Policy gradient: -advantage * log_prob(model_tokens), masked to
   assistant turns only

Usage:
    # Single GPU, from SFT checkpoint
    python scripts/grpo_train.py \
        --model /path/to/Qwen3-4B \
        --adapter checkpoints/sft-qwen3-4b-masked \
        --output checkpoints/grpo-qwen3-4b

    # Multi-GPU
    accelerate launch --num_processes 2 scripts/grpo_train.py \
        --model /path/to/Qwen3-4B \
        --adapter checkpoints/sft-qwen3-4b-masked
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from random import Random

# Offline mode: avoid hanging on HF hub checks for embedding models
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

sys.path.insert(0, str(Path(__file__).parent.parent))

from memorygym.adapters._common import (
    format_tool_result,
    get_system_prompt,
    parse_tool_calls,
)
from memorygym.training import MemoryEnv
from memorygym.training.common import strip_think


def strip_special_tokens(text: str) -> str:
    """Remove trailing special tokens."""
    for tag in ("<|im_end|>", "<|endoftext|>", "<|im_start|>"):
        text = text.replace(tag, "")
    return text.strip()


def run_episode(
    model,
    tokenizer,
    template: str,
    tier: str,
    seed: int,
    max_turns: int = 100,
    max_new_tokens: int = 512,
    temperature: float = 0.7,
    chat_kwargs: dict | None = None,
) -> tuple[list[dict], float, dict]:
    """Run a single episode, return (messages, reward, stats).

    messages: full conversation in OpenAI format
    reward: episode reward from env.get_verifiable_reward()
    stats: episode statistics dict
    """
    import torch

    env = MemoryEnv(template, tier=tier, seed=seed, reward_mode="shaped")
    obs = env.reset(seed=seed)
    system_prompt = get_system_prompt(env.write_budget)

    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": obs},
    ]

    done = False
    turn = 0
    info = {}
    chat_kwargs = chat_kwargs or {}
    verbose = os.environ.get("GRPO_VERBOSE", "0") == "1"
    last_event_idx = -1
    turns_on_event = 0
    max_turns_per_event = 5

    while not done and turn < max_turns:
        # Context window management: keep system + last N turns
        if len(context) > 24:
            context = context[:1] + context[-22:]

        # Stuck detection: auto-advance if too many turns on same event
        current_idx = env._event_idx
        if current_idx == last_event_idx:
            turns_on_event += 1
        else:
            turns_on_event = 0
            last_event_idx = current_idx

        if turns_on_event >= max_turns_per_event:
            current_type = (env._stream[current_idx]["type"]
                            if current_idx < len(env._stream) else None)
            if current_type != "question":
                _, _, done, info = env.step({"tool": "next"})
                turns_on_event = 0
                if done:
                    break
                next_obs = env._format_event(env._stream[env._event_idx])
                context.append({"role": "user", "content":
                    "[System: Moving to next event.]\n\n" + next_obs})
                turn += 1
                continue

        # Generate
        input_text = tokenizer.apply_chat_template(
            context, tokenize=False, add_generation_prompt=True,
            **chat_kwargs)
        inputs = tokenizer(
            input_text, return_tensors="pt",
            truncation=True, max_length=16384).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.95,
            )

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        raw_text = tokenizer.decode(new_tokens, skip_special_tokens=False)
        model_text = strip_special_tokens(strip_think(raw_text))

        context.append({"role": "assistant", "content": model_text})

        if verbose and turn % 5 == 0:
            event_type = "?"
            if env._event_idx < len(env._stream):
                event_type = env._stream[env._event_idx]["type"]
            print(f"    Turn {turn}: event={event_type} "
                  f"output={model_text[:80]}...", flush=True)

        # Parse and execute
        tool_calls = parse_tool_calls(model_text)

        if not tool_calls:
            _, _, done, info = env.step({"tool": "next"})
            if done:
                break
            next_obs = env._format_event(env._stream[env._event_idx])
            context.append({"role": "user", "content": next_obs})
        else:
            feedback_parts = []
            for action in tool_calls:
                obs_text, _, done, info = env.step(action)
                feedback_parts.append(format_tool_result(action, info))
                if done:
                    break
            feedback = "\n".join(feedback_parts)
            if not done:
                feedback += "\n\n" + obs_text
            context.append({"role": "user", "content": feedback})

        turn += 1

    reward = env.get_verifiable_reward()
    stats = info.get("episode_stats", {}) if info else {}
    if verbose:
        print(f"    Episode done: turns={turn} reward={reward:.3f} "
              f"correct={env._correct_count}/{env._total_questions} "
              f"writes={env._writes_used} "
              f"events_processed={env._event_idx}/{len(env._stream)}",
              flush=True)
    return context, reward, stats


def compute_grpo_loss(
    model,
    tokenizer,
    trajectories: list[tuple[list[dict], float]],
    max_length: int,
    chat_kwargs: dict | None = None,
    kl_coeff: float = 0.05,
    clip_eps: float = 0.2,
    clip_higher: float = 0.0,
):
    """Compute clipped GRPO policy gradient loss with optional KL penalty.

    When clip_higher > 0 (DAPO), uses asymmetric clipping:
        ratio clipped to [1 - clip_eps, 1 + clip_higher]
    Otherwise uses standard symmetric clipping:
        ratio clipped to [1 - clip_eps, 1 + clip_eps]

    ratio = exp(log_policy - log_ref) on assistant tokens.
    Loss = -min(ratio * A, clipped_ratio * A) + kl_coeff * KL

    Uses peft's disable_adapter_layers() to get reference logits without
    loading a separate model (reference = base + merged SFT, no GRPO LoRA).

    Args:
        model: The trainable peft model.
        tokenizer: Tokenizer.
        trajectories: List of (messages, advantage) tuples.
        max_length: Max sequence length for tokenization.
        chat_kwargs: Extra kwargs for apply_chat_template.
        kl_coeff: KL penalty coefficient (0 to disable).
        clip_eps: PPO-style clip epsilon (lower bound = 1 - clip_eps).
        clip_higher: DAPO Clip-Higher upper bound (0 = use clip_eps).
    """
    import torch
    import torch.nn.functional as F

    chat_kwargs = chat_kwargs or {}
    total_loss = None  # Accumulate grad-connected losses
    total_kl = 0.0
    n_valid = 0
    has_adapter = hasattr(model, "disable_adapter_layers")
    use_kl = kl_coeff > 0 and has_adapter
    # Clip-Higher needs reference logits for ratio computation
    clip_upper = (1.0 + clip_higher) if clip_higher > 0 else (1.0 + clip_eps)
    clip_lower = 1.0 - clip_eps

    for messages, advantage in trajectories:
        if abs(advantage) < 1e-6:
            continue  # Skip zero-advantage trajectories

        torch.cuda.empty_cache()

        # Tokenize full conversation
        try:
            full_text = tokenizer.apply_chat_template(
                messages, tokenize=False, **chat_kwargs)
        except TypeError:
            full_text = tokenizer.apply_chat_template(
                messages, tokenize=False)

        tokens = tokenizer(
            full_text, truncation=True, max_length=max_length,
            return_tensors="pt").to(model.device)
        input_ids = tokens["input_ids"]
        attention_mask = tokens["attention_mask"]

        # Build assistant-only mask
        labels = _build_assistant_mask(
            tokenizer, input_ids.squeeze(0), full_text)
        labels = labels.unsqueeze(0).to(model.device)

        # Forward pass (with LoRA = current policy)
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )
        logits = outputs.logits

        # Shift for next-token prediction
        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = labels[:, 1:].contiguous()

        # Per-token log probs
        log_probs = F.log_softmax(shift_logits, dim=-1)
        token_log_probs = log_probs.gather(
            2, shift_labels.clamp(min=0).unsqueeze(-1)).squeeze(-1)

        # Mask: only assistant tokens
        mask = (shift_labels != -100).float()
        n_tokens = mask.sum()
        if n_tokens < 1:
            continue

        # Get reference logits for ratio-based clipping and KL
        if has_adapter:
            with torch.no_grad():
                model.disable_adapter_layers()
                ref_outputs = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                )
                model.enable_adapter_layers()
                ref_log_probs = F.log_softmax(
                    ref_outputs.logits[:, :-1, :], dim=-1)
                ref_token_log_probs = ref_log_probs.gather(
                    2, shift_labels.clamp(min=0).unsqueeze(-1)).squeeze(-1)

            # Ratio = exp(log_policy - log_ref) per token
            log_ratio = (token_log_probs - ref_token_log_probs) * mask
            # Mean ratio across assistant tokens for stable clipping
            mean_log_ratio = log_ratio.sum() / n_tokens
            ratio = torch.exp(mean_log_ratio)

            # Clipped surrogate objective (PPO/GRPO style)
            clipped_ratio = torch.clamp(ratio, clip_lower, clip_upper)
            surr1 = ratio * advantage
            surr2 = clipped_ratio * advantage
            pg_loss = -torch.min(surr1, surr2)

            # KL penalty
            if use_kl:
                kl = mean_log_ratio  # KL ≈ E[log π - log π_ref]
                pg_loss = pg_loss + kl_coeff * kl
                total_kl += kl.item()
        else:
            # No adapter (fallback): REINFORCE-style, no clipping
            mean_log_prob = (token_log_probs * mask).sum() / n_tokens
            pg_loss = -advantage * mean_log_prob

        total_loss = pg_loss if total_loss is None else total_loss + pg_loss
        n_valid += 1

    if total_loss is None:
        total_loss = torch.tensor(0.0, device=model.device, requires_grad=True)
    elif n_valid > 1:
        total_loss = total_loss / n_valid

    mean_kl = total_kl / max(n_valid, 1)
    return total_loss, mean_kl


def _build_assistant_mask(tokenizer, input_ids, full_text):
    """Build labels tensor with -100 for non-assistant tokens."""
    import torch

    labels = torch.full_like(input_ids, -100)
    full_decoded = tokenizer.decode(input_ids, skip_special_tokens=False)

    marker_start = "<|im_start|>assistant"
    marker_end = "<|im_end|>"
    pos = 0
    spans = []
    while True:
        start = full_decoded.find(marker_start, pos)
        if start == -1:
            break
        content_start = full_decoded.find("\n", start) + 1
        end = full_decoded.find(marker_end, content_start)
        if end == -1:
            end = len(full_decoded)
        end += len(marker_end)
        spans.append((content_start, end))
        pos = end

    if not spans:
        return input_ids.clone()  # Fallback: train all

    for char_start, char_end in spans:
        prefix_toks = tokenizer(
            full_decoded[:char_start], add_special_tokens=False,
            return_tensors="pt")["input_ids"]
        tok_start = prefix_toks.shape[1]
        prefix_plus = tokenizer(
            full_decoded[:char_end], add_special_tokens=False,
            return_tensors="pt")["input_ids"]
        tok_end = min(prefix_plus.shape[1], len(input_ids))
        labels[tok_start:tok_end] = input_ids[tok_start:tok_end]

    return labels


def generate_episode_configs(
    n_configs: int,
    group_size: int,
    templates: list[str],
    tier: str,
    rng: Random,
) -> list[list[dict]]:
    """Generate grouped episode configs for GRPO.

    Returns list of groups, each group has `group_size` configs
    sharing the same (template, seed) but with different rng for sampling.
    """
    groups = []
    for _ in range(n_configs):
        template = rng.choice(templates)
        seed = rng.randint(0, 100000)
        group = [
            {"template": template, "tier": tier, "seed": seed,
             "sample_id": i}
            for i in range(group_size)
        ]
        groups.append(group)
    return groups


def main():
    parser = argparse.ArgumentParser(
        description="GRPO training for MemoryGym")
    parser.add_argument(
        "--model", required=True, help="Base model path")
    parser.add_argument(
        "--adapter", default=None,
        help="LoRA adapter to load (e.g., SFT checkpoint)")
    parser.add_argument(
        "--output", default="checkpoints/grpo",
        help="Output directory")
    parser.add_argument(
        "--lora-rank", type=int, default=16,
        help="LoRA rank for trainable adapter")
    parser.add_argument(
        "--steps", type=int, default=50,
        help="Number of training steps")
    parser.add_argument(
        "--group-size", type=int, default=4,
        help="G: episodes per scenario (GRPO group size)")
    parser.add_argument(
        "--groups-per-step", type=int, default=2,
        help="Number of scenario groups per training step")
    parser.add_argument(
        "--tier", default="lite", choices=["lite", "standard"],
        help="Evaluation tier")
    parser.add_argument(
        "--templates", nargs="+",
        default=["company", "research", "city",
                 "hospital", "sport", "movie",
                 "university", "codebase"],
        help="Templates to sample from")
    parser.add_argument(
        "--max-turns", type=int, default=100,
        help="Max turns per episode")
    parser.add_argument(
        "--max-new-tokens", type=int, default=512,
        help="Max new tokens per generation turn")
    parser.add_argument(
        "--max-length", type=int, default=8192,
        help="Max sequence length for training")
    parser.add_argument(
        "--lr", type=float, default=1e-5,
        help="Learning rate")
    parser.add_argument(
        "--temperature", type=float, default=0.7,
        help="Sampling temperature for rollouts")
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for config sampling")
    parser.add_argument(
        "--save-every", type=int, default=10,
        help="Save checkpoint every N steps")
    parser.add_argument(
        "--kl-coeff", type=float, default=0.05,
        help="KL penalty coefficient (0 to disable)")
    parser.add_argument(
        "--ips", action="store_true",
        help="Enable IPS-GRPO: inverse probability scaling to prevent mode collapse")
    parser.add_argument(
        "--clip-eps", type=float, default=0.2,
        help="PPO/GRPO clip epsilon (lower bound = 1-eps)")
    parser.add_argument(
        "--clip-higher", type=float, default=0.0,
        help="DAPO Clip-Higher: asymmetric upper clip (e.g., 0.28). "
             "0 = symmetric (use clip-eps for both bounds)")
    parser.add_argument(
        "--log-file", default=None,
        help="JSON log file path")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    is_distributed = int(os.environ.get("WORLD_SIZE", "1")) > 1
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    is_main = local_rank == 0

    # Load model
    if is_main:
        print(f"Loading model: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {
        "dtype": torch.bfloat16,
        "trust_remote_code": True,
    }
    if not is_distributed:
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)

    # Load SFT adapter if provided, then merge
    if args.adapter:
        if is_main:
            print(f"Loading SFT adapter: {args.adapter}")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
        model = model.merge_and_unload()
        if is_main:
            print("  SFT adapter merged")

    # Apply new trainable LoRA for GRPO
    if is_main:
        print(f"Adding LoRA (rank={args.lora_rank}) for GRPO training")
    from peft import LoraConfig, get_peft_model
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_rank * 2,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.0,  # No dropout for RL
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.gradient_checkpointing_enable()
    if is_main:
        model.print_trainable_parameters()

    # Detect Qwen3 thinking mode
    chat_kwargs = {}
    sig = inspect.signature(tokenizer.apply_chat_template)
    if "enable_thinking" in sig.parameters:
        chat_kwargs["enable_thinking"] = False
        if is_main:
            print("  (Qwen3 thinking mode disabled)")

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=0.01)

    # Training loop
    rng = Random(args.seed)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_entries = []

    if is_main:
        print(f"\n{'=' * 60}")
        print("GRPO Training")
        print(f"  Steps: {args.steps}")
        print(f"  Group size (G): {args.group_size}")
        print(f"  Groups/step: {args.groups_per_step}")
        print(f"  Episodes/step: {args.group_size * args.groups_per_step}")
        print(f"  Templates: {args.templates}")
        print(f"  Tier: {args.tier}")
        print(f"  LR: {args.lr}")
        clip_desc = f"eps={args.clip_eps}"
        if args.clip_higher > 0:
            clip_desc += f", DAPO clip-higher={args.clip_higher}"
        print(f"  Clipping: {clip_desc}")
        print(f"  IPS: {args.ips}, KL: {args.kl_coeff}")
        print(f"  Output: {output_dir}")
        print(f"{'=' * 60}\n")

    for step in range(args.steps):
        step_start = time.time()

        # Generate episode configs
        groups = generate_episode_configs(
            args.groups_per_step, args.group_size,
            args.templates, args.tier, rng)

        # Phase 1: Rollouts (no grad)
        model.eval()
        all_trajectories = []  # (messages, advantage)
        step_rewards = []
        step_stats = []

        if is_main:
            print(f"\n--- Step {step+1}/{args.steps}: Rollout phase ---",
                  flush=True)

        for group_idx, group in enumerate(groups):
            group_rewards = []
            group_messages = []

            for config in group:
                # Vary temperature slightly per sample for diversity
                temp = args.temperature + (config["sample_id"] - 1) * 0.1
                temp = max(0.3, min(1.2, temp))

                messages, reward, stats = run_episode(
                    model, tokenizer,
                    template=config["template"],
                    tier=config["tier"],
                    seed=config["seed"],
                    max_turns=args.max_turns,
                    max_new_tokens=args.max_new_tokens,
                    temperature=temp,
                    chat_kwargs=chat_kwargs,
                )
                group_rewards.append(reward)
                group_messages.append(messages)
                step_rewards.append(reward)
                step_stats.append(stats)

                if is_main:
                    correct = stats.get("correct_count", 0)
                    total_q = stats.get("total_questions", 0)
                    writes = stats.get("writes_used", 0)
                    n_msgs = len(messages)
                    # Debug: verify reward matches stats
                    expected_r = correct / total_q if total_q > 0 else 0.0
                    print(f"  [{step+1}/{args.steps}] "
                          f"G{group_idx}S{config['sample_id']} "
                          f"{config['template']}(s={config['seed']}): "
                          f"r={reward:.3f} "
                          f"(stats_correct/total={expected_r:.3f}) "
                          f"correct={correct}/{total_q} "
                          f"writes={writes} "
                          f"msgs={n_msgs}",
                          flush=True)

            # GRPO: compute advantages within group
            mean_r = sum(group_rewards) / len(group_rewards)
            std_r = (sum((r - mean_r) ** 2 for r in group_rewards)
                     / len(group_rewards)) ** 0.5
            eps = 1e-6

            if args.ips and len(group_rewards) > 1:
                # IPS-GRPO: inverse probability scaling (arXiv 2601.21669)
                # Discretize rewards to 0.05 buckets, weight by inverse freq
                bucket_size = 0.05
                buckets = [round(r / bucket_size) for r in group_rewards]
                bucket_counts = Counter(buckets)
                n = len(buckets)
                ips_weights = [n / bucket_counts[b] for b in buckets]
                # Normalize weights to mean=1
                w_mean = sum(ips_weights) / len(ips_weights)
                ips_weights = [w / w_mean for w in ips_weights]
            else:
                ips_weights = [1.0] * len(group_rewards)

            for messages, reward, w in zip(group_messages, group_rewards,
                                           ips_weights):
                advantage = (reward - mean_r) / (std_r + eps) * w
                all_trajectories.append((messages, advantage))

        # Phase 2: Training (with grad)
        torch.cuda.empty_cache()
        model.train()
        optimizer.zero_grad()

        loss, mean_kl = compute_grpo_loss(
            model, tokenizer, all_trajectories,
            max_length=args.max_length,
            chat_kwargs=chat_kwargs,
            kl_coeff=args.kl_coeff,
            clip_eps=args.clip_eps,
            clip_higher=args.clip_higher,
        )

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        torch.cuda.empty_cache()

        step_time = time.time() - step_start
        mean_reward = sum(step_rewards) / len(step_rewards)
        max_reward = max(step_rewards)
        mean_correct = sum(
            s.get("correct_count", 0) for s in step_stats
        ) / len(step_stats)

        if is_main:
            print(f"\n  Step {step+1}: loss={loss.item():.4f} "
                  f"kl={mean_kl:.4f} "
                  f"mean_r={mean_reward:.3f} max_r={max_reward:.3f} "
                  f"mean_correct={mean_correct:.1f} "
                  f"time={step_time:.0f}s\n")

        # Log
        entry = {
            "step": step + 1,
            "loss": loss.item(),
            "mean_kl": mean_kl,
            "mean_reward": mean_reward,
            "max_reward": max_reward,
            "mean_correct": mean_correct,
            "rewards": step_rewards,
            "time_s": step_time,
        }
        log_entries.append(entry)

        # Save
        if (step + 1) % args.save_every == 0 and is_main:
            ckpt_dir = output_dir / f"step-{step+1}"
            model.save_pretrained(str(ckpt_dir))
            tokenizer.save_pretrained(str(ckpt_dir))
            print(f"  Saved checkpoint: {ckpt_dir}")

    # Final save
    if is_main:
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))
        print(f"\nFinal model saved to {output_dir}")

        # Save training log
        log_path = args.log_file or str(output_dir / "training_log.json")
        with open(log_path, "w") as f:
            json.dump(log_entries, f, indent=2)
        print(f"Training log saved to {log_path}")

        # Summary
        print(f"\n{'=' * 60}")
        print("GRPO Training Complete")
        if log_entries:
            first_r = log_entries[0]["mean_reward"]
            last_r = log_entries[-1]["mean_reward"]
            print(f"  Reward: {first_r:.3f} → {last_r:.3f}")
            first_c = log_entries[0]["mean_correct"]
            last_c = log_entries[-1]["mean_correct"]
            print(f"  Correct: {first_c:.1f} → {last_c:.1f}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
