"""Unified training CLI: one entry point for data gen, SFT, and GRPO.

Usage:
    python -m memorygym.train data   [options]   # Generate SFT data
    python -m memorygym.train sft    [options]   # SFT (auto-generates data if needed)
    python -m memorygym.train grpo   [options]   # GRPO from SFT checkpoint
    python -m memorygym.train smoke  [options]   # GPU smoke test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


def _run_dir(mode: str, output: str | None = None) -> Path:
    """Create timestamped run directory."""
    if output:
        d = Path(output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        d = Path(f"runs/{mode}_{ts}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save_config(run_dir: Path, args: argparse.Namespace) -> None:
    """Save full config for reproducibility."""
    config = {k: v for k, v in vars(args).items() if v is not None}
    config["timestamp"] = datetime.now().isoformat()
    (run_dir / "config.json").write_text(json.dumps(config, indent=2))


# ── Data generation ──────────────────────────────────────────────────

def cmd_data(args: argparse.Namespace) -> int:
    from .env import generate_sft_trajectory
    from memorygym.simulation import TEMPLATES

    templates = args.templates or list(TEMPLATES.keys())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating SFT data: {len(templates)} templates × "
          f"{args.seeds} seeds = {len(templates) * args.seeds} trajectories")
    print(f"  Strategy: {args.strategy}")
    print(f"  Tier params: entities={args.n_entities}, "
          f"questions={args.n_questions}, corrections={args.n_corrections}")

    count = 0
    stats = {"templates": {}, "total_messages": 0, "total_trajectories": 0}

    with open(output, "w") as f:
        for tmpl in templates:
            tmpl_msgs = 0
            for seed in range(args.seeds):
                messages = generate_sft_trajectory(
                    tmpl, seed,
                    strategy=args.strategy,
                    n_entities=args.n_entities,
                    n_questions=args.n_questions,
                    n_corrections=args.n_corrections,
                    write_budget=args.write_budget,
                )
                f.write(json.dumps({"messages": messages}) + "\n")
                count += 1
                tmpl_msgs += len(messages)
            stats["templates"][tmpl] = {
                "trajectories": args.seeds,
                "total_messages": tmpl_msgs,
            }
            print(f"  {tmpl}: {args.seeds} trajectories, "
                  f"avg {tmpl_msgs // args.seeds} messages")

    stats["total_trajectories"] = count
    stats["total_messages"] = sum(
        t["total_messages"] for t in stats["templates"].values())
    print(f"\nSaved {count} trajectories to {output}")
    print(f"  Total messages: {stats['total_messages']}, "
          f"avg {stats['total_messages'] // count} per trajectory")

    # Save stats alongside data
    stats_path = output.with_suffix(".stats.json")
    stats_path.write_text(json.dumps(stats, indent=2))
    return 0


# ── SFT training ─────────────────────────────────────────────────────

def cmd_sft(args: argparse.Namespace) -> int:
    from .common import ensure_offline, load_model, build_assistant_mask
    from .common import get_chat_kwargs, apply_chat_template
    ensure_offline()

    run_dir = _run_dir("sft", args.output)
    _save_config(run_dir, args)

    # Auto-generate data if not provided
    data_path = args.data
    if not data_path or not Path(data_path).exists():
        print("No data file found — generating SFT data automatically...")
        data_path = str(run_dir / "data" / "sft_train.jsonl")
        Path(data_path).parent.mkdir(parents=True, exist_ok=True)
        # Reuse data generation with defaults
        data_args = argparse.Namespace(
            templates=args.templates,
            seeds=args.data_seeds,
            strategy="perfect",
            n_entities=args.n_entities,
            n_questions=args.n_questions,
            n_corrections=args.n_corrections,
            write_budget=args.write_budget,
            output=data_path,
        )
        cmd_data(data_args)
        print()

    # Load data
    print(f"Loading SFT data from {data_path}...")
    raw_data = []
    with open(data_path) as f:
        for line in f:
            if line.strip():
                raw_data.append(json.loads(line))
    print(f"  {len(raw_data)} trajectories")

    import torch
    from torch.utils.data import Dataset
    from transformers import Trainer, TrainingArguments

    is_distributed = int(os.environ.get("WORLD_SIZE", "1")) > 1
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    is_main = local_rank == 0

    # Load model
    print(f"Loading model: {args.model}")
    model, tokenizer = load_model(
        args.model,
        lora_rank=args.lora_rank if args.lora else None,
        distributed=is_distributed,
    )
    if args.lora and is_main:
        model.print_trainable_parameters()

    chat_kwargs = get_chat_kwargs(tokenizer)

    # Tokenize with assistant masking
    class SFTDataset(Dataset):
        def __init__(self, data, tokenizer, max_length):
            self.examples = []
            n_assistant = n_total = 0
            for item in data:
                full_text = apply_chat_template(
                    tokenizer, item["messages"], chat_kwargs)
                tokens = tokenizer(
                    full_text, truncation=True, max_length=max_length,
                    return_tensors="pt")
                input_ids = tokens["input_ids"].squeeze(0)
                attention_mask = tokens["attention_mask"].squeeze(0)
                if input_ids.shape[0] < 10:
                    continue
                labels = build_assistant_mask(
                    tokenizer, input_ids, full_text)
                n_total += input_ids.shape[0]
                n_assistant += (labels != -100).sum().item()
                self.examples.append({
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "labels": labels,
                })
            if is_main and n_total > 0:
                pct = 100 * n_assistant / n_total
                print(f"  Assistant tokens: {n_assistant}/{n_total} "
                      f"({pct:.1f}%)")

        def __len__(self):
            return len(self.examples)

        def __getitem__(self, idx):
            return self.examples[idx]

    dataset = SFTDataset(raw_data, tokenizer, args.max_length)
    print(f"  {len(dataset)} examples")

    # Training
    ckpt_dir = run_dir / "checkpoints"
    extra_args = {}
    if is_distributed:
        extra_args["ddp_find_unused_parameters"] = False

    training_args = TrainingArguments(
        output_dir=str(ckpt_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.1,
        bf16=True,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        gradient_checkpointing=True,
        report_to="none",
        dataloader_pin_memory=False,
        **extra_args,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    if is_main:
        n_gpus = int(os.environ.get("WORLD_SIZE", "1"))
        eff_batch = args.batch_size * args.grad_accum * n_gpus
        print(f"\nStarting SFT training:")
        print(f"  GPUs: {n_gpus}, Batch: {eff_batch}, "
              f"Epochs: {args.epochs}, LR: {args.lr}")
        print(f"  Output: {run_dir}\n")

    trainer.train()

    if is_main:
        final_dir = ckpt_dir / "final"
        model.save_pretrained(str(final_dir))
        tokenizer.save_pretrained(str(final_dir))
        print(f"\nModel saved to {final_dir}")

    return 0


# ── GRPO training ────────────────────────────────────────────────────

def cmd_grpo(args: argparse.Namespace) -> int:
    from .common import (
        ensure_offline, load_model, get_chat_kwargs,
        strip_think, strip_special_tokens, apply_chat_template,
        build_assistant_mask,
    )
    from .env import MemoryEnv
    from memorygym.adapters._common import (
        format_tool_result, get_system_prompt, parse_tool_calls,
    )
    ensure_offline()

    import torch
    import torch.nn.functional as F

    run_dir = _run_dir("grpo", args.output)
    _save_config(run_dir, args)

    is_main = int(os.environ.get("LOCAL_RANK", "0")) == 0
    is_distributed = int(os.environ.get("WORLD_SIZE", "1")) > 1

    # Load model with SFT adapter + new LoRA
    if is_main:
        print(f"Loading model: {args.model}")
        if args.adapter:
            print(f"  SFT adapter: {args.adapter}")
    model, tokenizer = load_model(
        args.model,
        adapter_path=args.adapter,
        lora_rank=args.lora_rank,
        distributed=is_distributed,
    )
    if is_main:
        model.print_trainable_parameters()

    chat_kwargs = get_chat_kwargs(tokenizer)
    if chat_kwargs and is_main:
        print("  (Qwen3 thinking mode disabled)")

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=0.01)

    templates = args.templates or [
        "company", "research", "city", "hospital", "sport", "movie",
        "university", "codebase", "project", "agentteam"]
    from random import Random
    rng = Random(args.seed)

    if is_main:
        print(f"\n{'=' * 60}")
        print(f"GRPO Training: {args.steps} steps, "
              f"G={args.group_size}, groups/step={args.groups_per_step}")
        print(f"  Templates: {templates}")
        clip_desc = f"eps={args.clip_eps}"
        if args.clip_higher > 0:
            clip_desc += f", DAPO clip-higher={args.clip_higher}"
        print(f"  Clipping: {clip_desc}")
        print(f"  IPS: {args.ips}, KL: {args.kl_coeff}")
        print(f"  Turn-level: {args.turn_level}, "
              f"Rollout max tokens: {args.rollout_max_tokens}")
        print(f"  Output: {run_dir}")
        print(f"{'=' * 60}\n")

    log_entries = []
    episodes_dir = run_dir / "episodes"
    episodes_dir.mkdir(exist_ok=True)

    for step in range(args.steps):
        step_start = time.time()
        all_trajectories = []
        step_rewards = []
        step_stats = []

        if is_main:
            print(f"--- Step {step+1}/{args.steps} ---", flush=True)

        # Rollout phase
        model.eval()
        for g_idx in range(args.groups_per_step):
            template = rng.choice(templates)
            seed = rng.randint(0, 100000)
            group_rewards = []
            group_messages = []
            group_stats = []

            for s_id in range(args.group_size):
                temp = args.temperature + (s_id - 1) * 0.1
                temp = max(0.3, min(1.2, temp))

                messages, reward, stats = _run_episode(
                    model, tokenizer, template, args.tier, seed,
                    max_turns=args.max_turns,
                    max_new_tokens=args.max_new_tokens,
                    temperature=temp,
                    chat_kwargs=chat_kwargs,
                    rollout_max_tokens=args.rollout_max_tokens,
                )
                group_rewards.append(reward)
                group_messages.append(messages)
                group_stats.append(stats)
                step_rewards.append(reward)
                step_stats.append(stats)

                if is_main:
                    c = stats.get("correct_count", 0)
                    t = stats.get("total_questions", 0)
                    w = stats.get("writes_used", 0)
                    print(f"  G{g_idx}S{s_id} {template}(s={seed}): "
                          f"r={reward:.3f} correct={c}/{t} "
                          f"writes={w}", flush=True)

            # GRPO advantages
            mean_r = sum(group_rewards) / len(group_rewards)
            std_r = (sum((r - mean_r) ** 2 for r in group_rewards)
                     / len(group_rewards)) ** 0.5
            eps = 1e-6

            if args.ips and len(group_rewards) > 1:
                # IPS-GRPO: inverse probability scaling (arXiv 2601.21669)
                from collections import Counter
                bucket_size = 0.05
                buckets = [round(r / bucket_size) for r in group_rewards]
                bucket_counts = Counter(buckets)
                n = len(buckets)
                ips_weights = [n / bucket_counts[b] for b in buckets]
                w_mean = sum(ips_weights) / len(ips_weights)
                ips_weights = [w / w_mean for w in ips_weights]
            else:
                ips_weights = [1.0] * len(group_rewards)

            for msgs, r, w, stats in zip(group_messages, group_rewards,
                                          ips_weights, group_stats):
                adv = (r - mean_r) / (std_r + eps) * w
                # Turn-level: per-turn advantage weights from shaped rewards
                turn_advs = None
                if getattr(args, 'turn_level', False):
                    tr = stats.get("turn_rewards", [])
                    if tr and any(abs(x) > 1e-8 for x in tr):
                        # Scale turn rewards into per-turn advantages:
                        # base = episode advantage, modulated by turn reward
                        tr_mean = sum(tr) / len(tr)
                        tr_std = (sum((x - tr_mean)**2 for x in tr)
                                  / len(tr)) ** 0.5 + eps
                        turn_advs = [
                            adv * (1.0 + (x - tr_mean) / tr_std)
                            for x in tr
                        ]
                all_trajectories.append((msgs, adv, turn_advs))

        # Training phase
        model.train()
        optimizer.zero_grad()

        loss, mean_kl = _compute_grpo_loss(
            model, tokenizer, all_trajectories,
            args.max_length, chat_kwargs,
            kl_coeff=args.kl_coeff,
            clip_eps=args.clip_eps,
            clip_higher=args.clip_higher,
        )
        if loss is not None:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        elapsed = time.time() - step_start
        mean_r = sum(step_rewards) / len(step_rewards)
        max_r = max(step_rewards)
        mean_c = sum(
            s.get("correct_count", 0) for s in step_stats
        ) / len(step_stats)

        entry = {
            "step": step + 1,
            "loss": loss.item() if loss is not None else 0.0,
            "mean_kl": mean_kl,
            "mean_reward": mean_r,
            "max_reward": max_r,
            "mean_correct": mean_c,
            "rewards": step_rewards,
            "time_s": elapsed,
        }
        log_entries.append(entry)

        if is_main:
            loss_val = loss.item() if loss is not None else 0.0
            print(f"  → loss={loss_val:.4f} kl={mean_kl:.4f} "
                  f"mean_r={mean_r:.3f} max_r={max_r:.3f} "
                  f"correct={mean_c:.1f} time={elapsed:.0f}s\n",
                  flush=True)

        # Save episode samples (best/worst)
        if is_main and (step + 1) % args.sample_every == 0:
            _save_episode_samples(
                episodes_dir, step + 1, all_trajectories, step_rewards)

        # Checkpoint
        if is_main and (step + 1) % args.save_every == 0:
            ckpt = run_dir / "checkpoints" / f"step-{step+1}"
            model.save_pretrained(str(ckpt))
            tokenizer.save_pretrained(str(ckpt))
            print(f"  Checkpoint: {ckpt}", flush=True)

    # Final save
    if is_main:
        final = run_dir / "checkpoints" / "final"
        final.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(final))
        tokenizer.save_pretrained(str(final))

        # Training log
        log_path = run_dir / "training_log.jsonl"
        with open(log_path, "w") as f:
            for e in log_entries:
                f.write(json.dumps(e) + "\n")

        # Summary metrics
        metrics = {
            "steps": args.steps,
            "first_reward": log_entries[0]["mean_reward"] if log_entries else 0,
            "last_reward": log_entries[-1]["mean_reward"] if log_entries else 0,
            "best_reward": max(e["max_reward"] for e in log_entries) if log_entries else 0,
            "first_correct": log_entries[0]["mean_correct"] if log_entries else 0,
            "last_correct": log_entries[-1]["mean_correct"] if log_entries else 0,
        }
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

        print(f"\n{'=' * 60}")
        print("GRPO Complete")
        print(f"  Reward: {metrics['first_reward']:.3f} → "
              f"{metrics['last_reward']:.3f}")
        print(f"  Correct: {metrics['first_correct']:.1f} → "
              f"{metrics['last_correct']:.1f}")
        print(f"  Output: {run_dir}")
        print(f"{'=' * 60}")

    return 0


def _run_episode(model, tokenizer, template, tier, seed,
                 max_turns=100, max_new_tokens=512,
                 temperature=0.7, chat_kwargs=None,
                 rollout_max_tokens=16384, backend_type="chromadb"):
    """Run a single MemoryEnv episode with the model."""
    import torch
    from .common import strip_think, strip_special_tokens
    from .env import MemoryEnv
    from memorygym.adapters._common import (
        format_tool_result, get_system_prompt, parse_tool_calls,
    )

    env = MemoryEnv(template, tier=tier, seed=seed, reward_mode="shaped",
                    backend_type=backend_type)
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
    last_event_idx = -1
    turns_on_event = 0
    max_turns_per_event = 5  # Auto-advance if stuck
    turn_rewards = []  # Per-turn shaped rewards for turn-level advantage

    while not done and turn < max_turns:
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
                # Auto-advance past non-question events
                _, _, done, info = env.step({"tool": "next"})
                turns_on_event = 0
                if done:
                    break
                next_obs = env._format_event(env._stream[env._event_idx])
                context.append({"role": "user", "content":
                    "[System: Moving to next event.]\n\n" + next_obs})
                turn += 1
                continue

        input_text = tokenizer.apply_chat_template(
            context, tokenize=False, add_generation_prompt=True,
            **chat_kwargs)
        inputs = tokenizer(
            input_text, return_tensors="pt",
            truncation=True, max_length=rollout_max_tokens).to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs, max_new_tokens=max_new_tokens,
                temperature=temperature, do_sample=True, top_p=0.95)

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(new_tokens, skip_special_tokens=False)
        model_text = strip_special_tokens(strip_think(raw))
        context.append({"role": "assistant", "content": model_text})

        tool_calls = parse_tool_calls(model_text)

        turn_reward = 0.0
        if not tool_calls:
            _, step_r, done, info = env.step({"tool": "next"})
            turn_reward += step_r
            if done:
                turn_rewards.append(turn_reward)
                break
            next_obs = env._format_event(env._stream[env._event_idx])
            context.append({"role": "user", "content": next_obs})
        else:
            parts = []
            for action in tool_calls:
                obs_text, step_r, done, info = env.step(action)
                turn_reward += step_r
                parts.append(format_tool_result(action, info))
                if done:
                    break
            feedback = "\n".join(parts)
            if not done:
                feedback += "\n\n" + obs_text
            context.append({"role": "user", "content": feedback})
        turn_rewards.append(turn_reward)

        turn += 1

    try:
        reward = env.get_verifiable_reward()
        stats = info.get("episode_stats", {}) if info else {}
        stats["turn_rewards"] = turn_rewards
        return context, reward, stats
    finally:
        env.close()


def _compute_grpo_loss(model, tokenizer, trajectories, max_length,
                       chat_kwargs=None, kl_coeff=0.05,
                       clip_eps=0.2, clip_higher=0.0):
    """Compute clipped GRPO policy gradient loss with optional KL penalty.

    When clip_higher > 0 (DAPO), uses asymmetric clipping:
        ratio clipped to [1 - clip_eps, 1 + clip_higher]
    Otherwise uses standard symmetric clipping:
        ratio clipped to [1 - clip_eps, 1 + clip_eps]

    Uses peft's disable_adapter_layers() for reference logits (zero-copy).
    """
    import torch
    import torch.nn.functional as F
    from .common import (build_assistant_mask, apply_chat_template,
                          build_turn_advantage_weights)

    chat_kwargs = chat_kwargs or {}
    total_loss = None
    total_kl = 0.0
    n_valid = 0
    n_skipped = 0
    n_total = len(trajectories)
    has_adapter = hasattr(model, "disable_adapter_layers")
    use_kl = kl_coeff > 0 and has_adapter
    clip_upper = (1.0 + clip_higher) if clip_higher > 0 else (1.0 + clip_eps)
    clip_lower = 1.0 - clip_eps

    for traj in trajectories:
        messages, advantage = traj[0], traj[1]
        turn_advs = traj[2] if len(traj) > 2 else None
        if abs(advantage) < 1e-6:
            n_skipped += 1
            continue

        full_text = apply_chat_template(tokenizer, messages, chat_kwargs)
        tokens = tokenizer(
            full_text, truncation=True, max_length=max_length,
            return_tensors="pt").to(model.device)
        input_ids = tokens["input_ids"]
        attention_mask = tokens["attention_mask"]
        labels = build_assistant_mask(
            tokenizer, input_ids.squeeze(0), full_text
        ).unsqueeze(0).to(model.device)

        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        logits = outputs.logits
        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = labels[:, 1:].contiguous()

        log_probs = F.log_softmax(shift_logits, dim=-1)
        token_log_probs = log_probs.gather(
            2, shift_labels.clamp(min=0).unsqueeze(-1)).squeeze(-1)
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

            # Per-token ratio = exp(log_policy - log_ref)
            log_ratio = (token_log_probs - ref_token_log_probs) * mask
            ratio = torch.exp(log_ratio)

            # Per-token clipped surrogate objective (GRPO style)
            clipped_ratio = torch.clamp(ratio, clip_lower, clip_upper)

            # Turn-level: per-token advantage from turn rewards
            if turn_advs is not None:
                adv_weights = build_turn_advantage_weights(
                    tokenizer, input_ids.squeeze(0), turn_advs
                )[1:].unsqueeze(0).to(model.device)  # shift by 1 to align
                # Where no turn advantage mapped, fall back to scalar
                no_turn = (adv_weights == 0) & (mask > 0)
                adv_weights[no_turn] = advantage
                token_adv = adv_weights
            else:
                token_adv = advantage

            surr1 = ratio * token_adv
            surr2 = clipped_ratio * token_adv
            pg_loss = -(torch.min(surr1, surr2) * mask).sum() / n_tokens

            # KL penalty: Schulman k3 estimator (r - 1) - log(r), always >= 0
            if use_kl:
                per_token_kl = ((ratio - 1) - log_ratio) * mask
                kl = per_token_kl.sum() / n_tokens
                pg_loss = pg_loss + kl_coeff * kl
                total_kl += kl.item()
        else:
            # No adapter (fallback): REINFORCE-style, no clipping
            mean_log_prob = (token_log_probs * mask).sum() / n_tokens
            pg_loss = -advantage * mean_log_prob

        total_loss = pg_loss if total_loss is None else total_loss + pg_loss
        n_valid += 1

    if n_skipped > 0:
        print(f"[GRPO] {n_valid}/{n_total} trajectories used "
              f"(skipped {n_skipped} with |advantage| < 1e-6)")

    if total_loss is None:
        print("[GRPO] WARNING: step skipped — all trajectories filtered")
        mean_kl = total_kl / max(n_valid, 1)
        return None, mean_kl

    if n_valid >= 1:
        total_loss = total_loss / n_valid

    mean_kl = total_kl / max(n_valid, 1)
    return total_loss, mean_kl


def _save_episode_samples(episodes_dir, step, trajectories, rewards):
    """Save best and worst episode traces for debugging."""
    if not rewards:
        return
    best_idx = rewards.index(max(rewards))
    worst_idx = rewards.index(min(rewards))
    for label, idx in [("best", best_idx), ("worst", worst_idx)]:
        traj = trajectories[idx]
        msgs, adv = traj[0], traj[1]
        data = {
            "step": step,
            "label": label,
            "reward": rewards[idx],
            "advantage": adv,
            "n_messages": len(msgs),
            "messages": msgs,
        }
        path = episodes_dir / f"step_{step:03d}_{label}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ── Smoke test ───────────────────────────────────────────────────────

def cmd_smoke(args: argparse.Namespace) -> int:
    """Quick pipeline validation."""
    from .env import MemoryEnv
    from memorygym.adapters._common import parse_tool_calls
    from memorygym.simulation import TEMPLATES

    print("=" * 60)
    print("Pipeline smoke test")
    print("=" * 60)

    # 1. MemoryEnv
    print("\n[1/3] MemoryEnv...")
    env = MemoryEnv("company", tier="lite", seed=42, reward_mode="shaped")
    obs = env.reset(seed=42)
    assert "Event" in obs or "DOCUMENTS" in obs
    print(f"  OK — {len(env._stream)} events")

    # 2. Tool parsing
    print("\n[2/3] Tool call parsing...")
    tests = [
        ('<tool_call>{"name": "Write", "arguments": '
         '{"content": "test"}}</tool_call>', 1),
        ('```json\n{"name": "memory_search", "arguments": '
         '{"query": "test"}}\n```', 1),
        ("I'll think about this...", 0),
    ]
    for text, expected in tests:
        assert len(parse_tool_calls(text)) == expected
    print("  OK — all formats parsed")

    # 3. Multi-template
    print("\n[3/3] Templates...")
    for tmpl in sorted(TEMPLATES.keys()):
        env = MemoryEnv(tmpl, tier="lite", seed=0)
        obs = env.reset(seed=0)
        print(f"  {tmpl}: {len(env._stream)} events")

    print(f"\n{'=' * 60}")
    print("SMOKE TEST PASSED")
    print("=" * 60)
    return 0


# ── Main CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="memorygym.train",
        description="MemoryGym training pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- data --
    p_data = sub.add_parser("data", help="Generate SFT training data")
    p_data.add_argument("--output", "-o", default="data/sft_train.jsonl",
                        help="Output JSONL path (default: data/sft_train.jsonl)")
    p_data.add_argument("--seeds", type=int, default=20,
                        help="Number of seeds per template (default: 20)")
    p_data.add_argument("--templates", nargs="+", default=None,
                        help="Templates to use (default: all 10)")
    p_data.add_argument("--strategy", default="perfect",
                        choices=["perfect", "strategic"],
                        help="Trajectory strategy (default: perfect)")
    p_data.add_argument("--n-entities", type=int, default=60,
                        help="Entities per world (default: 60)")
    p_data.add_argument("--n-questions", type=int, default=20,
                        help="Questions per eval (default: 20)")
    p_data.add_argument("--n-corrections", type=int, default=5,
                        help="Corrections per eval (default: 5)")
    p_data.add_argument("--write-budget", type=int, default=30,
                        help="Write budget for agent (default: 30)")

    # -- sft --
    p_sft = sub.add_parser("sft", help="SFT training (auto-generates data)")
    p_sft.add_argument("--model", required=True)
    p_sft.add_argument("--data", default=None,
                        help="Pre-generated data (auto-gen if omitted)")
    p_sft.add_argument("--output", "-o", default=None)
    p_sft.add_argument("--lora", action="store_true")
    p_sft.add_argument("--lora-rank", type=int, default=64)
    p_sft.add_argument("--epochs", type=int, default=3)
    p_sft.add_argument("--batch-size", type=int, default=1)
    p_sft.add_argument("--grad-accum", type=int, default=8)
    p_sft.add_argument("--lr", type=float, default=2e-5)
    p_sft.add_argument("--max-length", type=int, default=8192)
    p_sft.add_argument("--templates", nargs="+", default=None)
    p_sft.add_argument("--data-seeds", type=int, default=20,
                        help="Seeds for auto data generation")
    p_sft.add_argument("--n-entities", type=int, default=60)
    p_sft.add_argument("--n-questions", type=int, default=20)
    p_sft.add_argument("--n-corrections", type=int, default=5)
    p_sft.add_argument("--write-budget", type=int, default=30)

    # -- grpo --
    p_grpo = sub.add_parser("grpo", help="GRPO RL training")
    p_grpo.add_argument("--model", required=True)
    p_grpo.add_argument("--adapter", default=None,
                         help="SFT adapter checkpoint")
    p_grpo.add_argument("--output", "-o", default=None)
    p_grpo.add_argument("--lora-rank", type=int, default=16)
    p_grpo.add_argument("--steps", type=int, default=50)
    p_grpo.add_argument("--group-size", type=int, default=4)
    p_grpo.add_argument("--groups-per-step", type=int, default=2)
    p_grpo.add_argument("--tier", default="lite",
                         choices=["lite", "standard"])
    p_grpo.add_argument("--templates", nargs="+", default=None)
    p_grpo.add_argument("--max-turns", type=int, default=100)
    p_grpo.add_argument("--max-new-tokens", type=int, default=512)
    p_grpo.add_argument("--lr", type=float, default=1e-5)
    p_grpo.add_argument("--temperature", type=float, default=0.7)
    p_grpo.add_argument("--max-length", type=int, default=8192)
    p_grpo.add_argument("--seed", type=int, default=42)
    p_grpo.add_argument("--save-every", type=int, default=10)
    p_grpo.add_argument("--sample-every", type=int, default=5,
                         help="Save episode samples every N steps")
    p_grpo.add_argument("--kl-coeff", type=float, default=0.05,
                         help="KL penalty coefficient (0 to disable)")
    p_grpo.add_argument("--ips", action="store_true",
                         help="Enable IPS-GRPO: inverse probability scaling")
    p_grpo.add_argument("--clip-eps", type=float, default=0.2,
                         help="PPO/GRPO clip epsilon")
    p_grpo.add_argument("--clip-higher", type=float, default=0.0,
                         help="DAPO Clip-Higher asymmetric upper clip")
    p_grpo.add_argument("--rollout-max-tokens", type=int, default=16384,
                         help="Max token length for rollout context truncation")
    p_grpo.add_argument("--turn-level", action="store_true",
                         help="Use turn-level advantage (mix episode + shaped reward)")

    # -- smoke --
    sub.add_parser("smoke", help="Quick pipeline validation (no GPU)")

    args = parser.parse_args()

    handlers = {
        "data": cmd_data,
        "sft": cmd_sft,
        "grpo": cmd_grpo,
        "smoke": cmd_smoke,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
