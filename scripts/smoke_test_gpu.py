#!/usr/bin/env python3
"""GPU smoke test: validate full training pipeline with a small model.

Runs a single MemoryEnv episode with a real (tiny) LLM to verify:
1. MemoryEnv reset/step works end-to-end
2. Tool call parsing handles real model output
3. SFT trajectory generation works
4. ChromaDB embedding search works under real conditions

Usage (on GPU machine):
    # Quick smoke test (~2 min, 0.5B model)
    python scripts/smoke_test_gpu.py

    # With specific model
    python scripts/smoke_test_gpu.py --model Qwen/Qwen3-0.6B

    # Dry run (no GPU, just validates pipeline logic)
    python scripts/smoke_test_gpu.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Offline mode: avoid hanging on HF hub checks for embedding models
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memorygym.adapters._common import (
    format_tool_result,
    get_system_prompt,
    parse_tool_calls,
)
from memorygym.training import MemoryEnv, generate_sft_trajectory
from memorygym.training.common import strip_think


def run_dry_smoke(tier: str = "lite") -> dict:
    """Pipeline validation without GPU — tests env + tool parsing."""
    print("=" * 60)
    print("DRY RUN: Testing pipeline logic (no GPU)")
    print("=" * 60)

    results = {"steps": []}

    # 1. MemoryEnv reset
    print("\n[1/5] MemoryEnv reset...")
    env = MemoryEnv("company", tier=tier, seed=42, reward_mode="shaped")
    obs = env.reset(seed=42)
    assert "DOCUMENTS" in obs or "Event" in obs, f"Bad initial obs: {obs[:100]}"
    print(f"  OK — {len(env._stream)} events in stream")
    from collections import Counter
    event_types = Counter(e["type"] for e in env._stream)
    print(f"  Event types: {dict(event_types)}")

    # 2. Step through with mock actions
    print("\n[2/5] Step through episode...")
    done = False
    step_count = 0
    stores = 0
    searches = 0
    answers = 0
    rewards = []

    while not done and step_count < 300:
        event = env._stream[env._event_idx] if env._event_idx < len(env._stream) else None
        if event is None:
            break

        etype = event["type"]

        if etype == "ingest":
            # Store first entity from batch
            names = event.get("entity_names", [])
            if names and stores < env.write_budget:
                _, r, done, info = env.step({
                    "tool": "memory_store",
                    "args": {"content": f"{names[0]} | test data"},
                })
                stores += 1
                rewards.append(r)
            _, r, done, _ = env.step({"tool": "next"})

        elif etype == "correction":
            # Search → forget → store (correction flow)
            _, r, done, info = env.step({
                "tool": "memory_search",
                "args": {"query": event["entity_name"]},
            })
            searches += 1
            if info.get("results"):
                mid = info["results"][0]["id"]
                _, r, done, _ = env.step({
                    "tool": "memory_forget",
                    "args": {"memory_id": mid},
                })
                if not done and stores < env.write_budget:
                    _, r, done, _ = env.step({
                        "tool": "memory_store",
                        "args": {"content": f"{event['entity_name']} | updated"},
                    })
                    stores += 1
                    rewards.append(r)
            _, r, done, _ = env.step({"tool": "next"})

        elif etype == "question":
            # Search then answer
            _, _, done, info = env.step({
                "tool": "memory_search",
                "args": {"query": event.get("question", "")[:50]},
            })
            searches += 1
            if not done:
                _, r, done, _ = env.step({
                    "tool": "submit_answer",
                    "args": {"answer": "I don't have enough information"},
                })
                answers += 1
                rewards.append(r)

        else:
            # noise, session_break, etc.
            _, _, done, _ = env.step({"tool": "next"})

        step_count += 1

    episode_reward = env.get_verifiable_reward()
    print(f"  OK — {step_count} steps, {stores} stores, "
          f"{searches} searches, {answers} answers")
    print(f"  Episode reward: {episode_reward:.2f}")
    print(f"  Shaped rewards: {sum(r for r in rewards if r > 0):.2f} "
          f"positive, {sum(r for r in rewards if r < 0):.2f} negative")

    # 3. Tool call parsing
    print("\n[3/5] Tool call parsing...")
    test_outputs = [
        '<tool_call>{"name": "memory_store", "arguments": {"content": "test"}}</tool_call>',
        '```json\n{"name": "memory_search", "arguments": {"query": "test"}}\n```',
        '{"name": "submit_answer", "arguments": {"answer": "42"}}',
        "I'll think about this first...",  # no tool call
    ]
    for i, text in enumerate(test_outputs):
        calls = parse_tool_calls(text)
        expected = 1 if i < 3 else 0
        assert len(calls) == expected, f"Parse {i}: expected {expected}, got {len(calls)}"
    print("  OK — all 4 formats parsed correctly")

    # 4. SFT trajectory
    print("\n[4/5] SFT trajectory generation...")
    messages = generate_sft_trajectory("company", seed=0)
    roles = [m["role"] for m in messages]
    assert roles[0] == "system"
    # Check noise events are included
    info_msgs = [m for m in messages if m["role"] == "user" and "[INFO]" in m["content"]]
    print(f"  OK — {len(messages)} messages, {len(info_msgs)} noise events")

    # 5. Multi-template
    print("\n[5/5] Multi-template validation...")
    for tmpl in ("company", "research", "city", "hospital", "sport", "movie"):
        env = MemoryEnv(tmpl, tier="lite", seed=0)
        obs = env.reset(seed=0)
        assert "Event" in obs
        n_events = len(env._stream)
        print(f"  {tmpl}: {n_events} events")

    print("\n" + "=" * 60)
    print("DRY RUN PASSED — pipeline logic OK")
    print("=" * 60)
    return {"status": "pass", "steps": step_count, "reward": episode_reward}




def run_gpu_smoke(model_name: str, tier: str = "lite",
                  adapter: str | None = None) -> dict:
    """Full GPU smoke test with a real LLM."""
    print("=" * 60)
    label = f"{model_name}" + (f" + {adapter}" if adapter else "")
    print(f"GPU SMOKE TEST: {label}")
    print("=" * 60)

    # Import torch/transformers
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("ERROR: torch/transformers not installed")
        return {"status": "fail", "error": "missing dependencies"}

    # Check GPU
    if not torch.cuda.is_available():
        print("ERROR: No GPU available")
        return {"status": "fail", "error": "no GPU"}

    gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
    gpu_free = (torch.cuda.get_device_properties(0).total_memory
                - torch.cuda.memory_reserved(0)) / 1e9
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Memory: {gpu_free:.1f}GB free / {gpu_mem:.1f}GB total")

    # Load model
    print(f"\nLoading {model_name}...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    if adapter:
        print(f"Loading LoRA adapter from {adapter}...")
        try:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, adapter)
            model = model.merge_and_unload()
            print("  LoRA merged successfully")
        except ImportError:
            print("ERROR: peft required for --adapter")
            return {"status": "fail", "error": "missing peft"}

    load_time = time.time() - t0
    print(f"  Loaded in {load_time:.1f}s")

    # Set up env
    env = MemoryEnv("company", tier=tier, seed=42, reward_mode="shaped")
    obs = env.reset(seed=42)
    system_prompt = get_system_prompt(env.write_budget)

    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": obs},
    ]

    done = False
    turn = 0
    max_turns = 200  # Full episode
    total_tool_calls = 0
    total_gen_time = 0.0
    max_ctx_tokens = 16384  # Truncate context to avoid OOM

    print(f"\nRunning episode ({len(env._stream)} events, max {max_turns} turns)...")

    # Detect Qwen3 thinking mode — disable it for tool-calling
    chat_kwargs = {}
    if hasattr(tokenizer, "apply_chat_template"):
        import inspect
        sig = inspect.signature(tokenizer.apply_chat_template)
        if "enable_thinking" in sig.parameters:
            chat_kwargs["enable_thinking"] = False
            print("  (Qwen3 thinking mode disabled for tool-calling)")

    degenerate_count = 0
    last_output = ""

    while not done and turn < max_turns:
        # Context window management: keep system + last N turns
        if len(context) > 20:
            context = context[:1] + context[-18:]  # system + recent turns

        # Generate
        t0 = time.time()
        input_text = tokenizer.apply_chat_template(
            context, tokenize=False, add_generation_prompt=True,
            **chat_kwargs)
        inputs = tokenizer(input_text, return_tensors="pt",
                           truncation=True,
                           max_length=max_ctx_tokens).to(model.device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.7,
                do_sample=True,
                top_p=0.95,
            )
        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        # Decode with special tokens to preserve <tool_call> tags
        raw_text = tokenizer.decode(new_tokens, skip_special_tokens=False)
        # Strip <think> blocks and trailing special tokens
        model_text = strip_think(raw_text)
        # Remove trailing special tokens like <|im_end|>
        for tag in ("<|im_end|>", "<|endoftext|>"):
            model_text = model_text.replace(tag, "")
        gen_time = time.time() - t0
        total_gen_time += gen_time

        context.append({"role": "assistant", "content": model_text})

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
                total_tool_calls += 1
                if done:
                    break
            feedback = "\n".join(feedback_parts)
            if not done:
                feedback += "\n\n" + obs_text
            context.append({"role": "user", "content": feedback})

        turn += 1

        if turn % 10 == 0:
            stats = info.get("episode_stats", {})
            print(f"  Turn {turn}: writes={stats.get('writes_used', 0)}, "
                  f"correct={stats.get('correct_count', 0)}/"
                  f"{stats.get('questions_answered', 0)}")

    # Results
    reward = env.get_verifiable_reward()
    stats = info.get("episode_stats", {}) if info else {}

    print(f"\n{'=' * 60}")
    print("RESULTS:")
    print(f"  Turns: {turn}")
    print(f"  Tool calls: {total_tool_calls}")
    print(f"  Writes: {stats.get('writes_used', 0)}/{env.write_budget}")
    print(f"  Correct: {stats.get('correct_count', 0)}/"
          f"{stats.get('total_questions', 0)}")
    print(f"  Reward: {reward:.2f}")
    print(f"  Avg gen time: {total_gen_time/max(turn,1):.2f}s/turn")
    print(f"  Total time: {total_gen_time:.1f}s")

    status = "pass" if total_tool_calls > 0 else "warn_no_tools"
    print(f"\nSTATUS: {status.upper()}")
    if status == "warn_no_tools":
        print("  WARNING: Model made no tool calls — may need prompt tuning")
    print("=" * 60)

    return {
        "status": status,
        "model": model_name,
        "turns": turn,
        "tool_calls": total_tool_calls,
        "reward": reward,
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(
        description="GPU smoke test for MemoryGym training pipeline")
    parser.add_argument(
        "--model", default="Qwen/Qwen3-0.6B",
        help="HuggingFace model name (default: Qwen/Qwen3-0.6B)")
    parser.add_argument(
        "--adapter", default=None,
        help="LoRA adapter checkpoint path (optional)")
    parser.add_argument(
        "--tier", default="lite", choices=["lite", "standard"],
        help="Evaluation tier")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No GPU, just validate pipeline logic")
    args = parser.parse_args()

    if args.dry_run:
        result = run_dry_smoke(args.tier)
    else:
        result = run_gpu_smoke(args.model, args.tier, adapter=args.adapter)

    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
