#!/usr/bin/env python3
"""Test SFT-trained model inference: does it produce <tool_call> tags?

Usage:
    python3 scripts/test_sft_inference.py \
        --base-model /path/to/Qwen3-4B \
        --adapter checkpoints/sft-qwen3-4b-masked
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", required=True, help="Base model path")
    parser.add_argument("--adapter", required=True,
                        help="LoRA adapter checkpoint path")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading tokenizer from {args.base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model, trust_remote_code=True)

    print(f"Loading base model from {args.base_model}...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    print(f"Loading LoRA adapter from {args.adapter}...")
    try:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
        model = model.merge_and_unload()
        print("  LoRA merged successfully")
    except ImportError:
        print("ERROR: peft required for LoRA adapter loading")
        sys.exit(1)

    # Detect Qwen3 thinking mode
    import inspect
    chat_kwargs = {}
    sig = inspect.signature(tokenizer.apply_chat_template)
    if "enable_thinking" in sig.parameters:
        chat_kwargs["enable_thinking"] = False
        print("  (Qwen3 thinking mode disabled)")

    # Build a test prompt mimicking the SFT data format
    from memorygym.training import generate_sft_trajectory
    msgs = generate_sft_trajectory(
        "company", seed=99, n_entities=10, n_questions=3,
        n_corrections=2, write_budget=8)

    # Take system + first user message only (the ingest event)
    test_messages = [msgs[0], msgs[1]]

    print("\n--- Test prompt (system + first user) ---")
    print(f"System: {msgs[0]['content'][:200]}...")
    print(f"User: {msgs[1]['content'][:200]}...")

    # Generate
    input_text = tokenizer.apply_chat_template(
        test_messages, tokenize=False, add_generation_prompt=True,
        **chat_kwargs)
    inputs = tokenizer(input_text, return_tensors="pt",
                       truncation=True, max_length=4096).to(model.device)

    print(f"\nInput tokens: {inputs['input_ids'].shape[1]}")
    print("Generating...")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            temperature=0.3,
            do_sample=True,
            top_p=0.95,
        )

    new_tokens = outputs[0][inputs["input_ids"].shape[1]:]

    # Decode with and without special tokens
    text_with_special = tokenizer.decode(new_tokens, skip_special_tokens=False)
    text_clean = tokenizer.decode(new_tokens, skip_special_tokens=True)

    print("\n--- Raw output (with special tokens) ---")
    print(text_with_special[:1000])
    print("\n--- Clean output (skip_special_tokens=True) ---")
    print(text_clean[:1000])

    # Check for tool calls
    from memorygym.adapters._common import parse_tool_calls
    calls = parse_tool_calls(text_clean)
    calls_raw = parse_tool_calls(text_with_special)

    print(f"\n--- Tool call detection ---")
    print(f"  From clean text: {len(calls)} tool calls")
    print(f"  From raw text:   {len(calls_raw)} tool calls")

    if calls:
        print("  SUCCESS: Model produces tool calls!")
        for c in calls[:3]:
            print(f"    {c}")
    elif calls_raw:
        print("  PARTIAL: Tool calls exist in raw but stripped by skip_special_tokens")
        for c in calls_raw[:3]:
            print(f"    {c}")
    else:
        print("  FAIL: No tool calls detected")

    # Also test with a question prompt
    print("\n\n--- Test 2: Question prompt ---")
    q_messages = [
        msgs[0],  # system
        {"role": "user", "content": (
            '=== Event 1/1 [QUESTION] ===\n\n'
            '**Question:**\n'
            'What is Atlas Systems\'s dividend yield?\n\n'
            'Search your memory and call submit_answer(answer="...").'
        )},
    ]
    input_text2 = tokenizer.apply_chat_template(
        q_messages, tokenize=False, add_generation_prompt=True,
        **chat_kwargs)
    inputs2 = tokenizer(input_text2, return_tensors="pt",
                        truncation=True, max_length=4096).to(model.device)

    with torch.no_grad():
        outputs2 = model.generate(
            **inputs2,
            max_new_tokens=args.max_new_tokens,
            temperature=0.3,
            do_sample=True,
        )

    new_tokens2 = outputs2[0][inputs2["input_ids"].shape[1]:]
    text2 = tokenizer.decode(new_tokens2, skip_special_tokens=True)
    print(text2[:500])
    calls2 = parse_tool_calls(text2)
    print(f"  Tool calls: {len(calls2)}")
    if calls2:
        for c in calls2[:3]:
            print(f"    {c}")


if __name__ == "__main__":
    main()
