#!/usr/bin/env python3
"""SFT training script for MemoryGym tool-calling.

Fine-tunes a model on perfect/strategic simulation trajectories
to teach tool-calling patterns (memory_store, memory_search,
memory_forget, submit_answer).

Supports single-GPU (direct) and multi-GPU (via accelerate/torchrun).

Usage:
    # Single GPU
    python scripts/sft_train.py --model /path/to/Qwen3-4B --data data/sft_train.jsonl --lora

    # Multi-GPU via accelerate
    accelerate launch --num_processes 2 scripts/sft_train.py --model /path/to/Qwen3-4B --data data/sft_train.jsonl --lora
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_sft_data(path: str) -> list[dict]:
    """Load JSONL SFT data: each line = {"messages": [...]}."""
    data = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


def build_masked_labels(tokenizer, messages, max_length, torch_module):
    """Build input_ids with labels masked to -100 for non-assistant tokens.

    Only assistant turns contribute to the loss — system/user tokens are
    masked so the model learns tool-calling, not document parroting.
    """
    import inspect

    chat_kwargs = {}
    try:
        sig = inspect.signature(tokenizer.apply_chat_template)
        if "enable_thinking" in sig.parameters:
            chat_kwargs["enable_thinking"] = False
    except (TypeError, ValueError):
        pass

    try:
        full_text = tokenizer.apply_chat_template(
            messages, tokenize=False, **chat_kwargs)
    except TypeError:
        full_text = tokenizer.apply_chat_template(
            messages, tokenize=False)

    tokens = tokenizer(
        full_text, truncation=True, max_length=max_length,
        return_tensors="pt")
    input_ids = tokens["input_ids"].squeeze(0)
    attention_mask = tokens["attention_mask"].squeeze(0)

    # Default: mask everything
    labels = torch_module.full_like(input_ids, -100)

    # Find assistant turn boundaries in decoded text
    full_decoded = tokenizer.decode(input_ids, skip_special_tokens=False)

    marker_start = "<|im_start|>assistant"
    marker_end = "<|im_end|>"
    pos = 0
    assistant_spans = []
    while True:
        start = full_decoded.find(marker_start, pos)
        if start == -1:
            break
        content_start = full_decoded.find("\n", start) + 1
        end = full_decoded.find(marker_end, content_start)
        if end == -1:
            end = len(full_decoded)
        end += len(marker_end)
        assistant_spans.append((content_start, end))
        pos = end

    if not assistant_spans:
        # Fallback: train on everything (non-Qwen models)
        labels = input_ids.clone()
    else:
        for char_start, char_end in assistant_spans:
            prefix_toks = tokenizer(
                full_decoded[:char_start], add_special_tokens=False,
                return_tensors="pt")["input_ids"]
            tok_start = prefix_toks.shape[1]
            prefix_plus_toks = tokenizer(
                full_decoded[:char_end], add_special_tokens=False,
                return_tensors="pt")["input_ids"]
            tok_end = min(prefix_plus_toks.shape[1], len(input_ids))
            labels[tok_start:tok_end] = input_ids[tok_start:tok_end]

    return input_ids, attention_mask, labels


def main():
    parser = argparse.ArgumentParser(description="SFT training for MemoryGym")
    parser.add_argument("--model", required=True, help="Base model path")
    parser.add_argument("--data", required=True, help="SFT JSONL data path")
    parser.add_argument("--output", default="checkpoints/sft",
                        help="Output directory")
    parser.add_argument("--lora", action="store_true",
                        help="Use LoRA (saves ~60%% memory)")
    parser.add_argument("--lora-rank", type=int, default=64,
                        help="LoRA rank")
    parser.add_argument("--epochs", type=int, default=3,
                        help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=1,
                        help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=8,
                        help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=2e-5,
                        help="Learning rate")
    parser.add_argument("--max-length", type=int, default=4096,
                        help="Max sequence length")
    parser.add_argument("--bf16", action="store_true", default=True,
                        help="Use bfloat16 (default)")
    args = parser.parse_args()

    import torch
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )
    from torch.utils.data import Dataset

    is_distributed = int(os.environ.get("WORLD_SIZE", "1")) > 1
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    is_main = local_rank == 0

    if is_main:
        print(f"Loading tokenizer from {args.model}...")
    tokenizer = AutoTokenizer.from_pretrained(
        args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if is_main:
        print(f"Loading model from {args.model}...")
    model_kwargs = {
        "dtype": torch.bfloat16 if args.bf16 else torch.float32,
        "trust_remote_code": True,
    }
    if not is_distributed:
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)

    if args.lora:
        try:
            from peft import LoraConfig, get_peft_model
        except ImportError:
            print("ERROR: peft required for --lora. "
                  "Install with: pip install peft")
            sys.exit(1)

        lora_config = LoraConfig(
            r=args.lora_rank,
            lora_alpha=args.lora_rank * 2,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        if is_main:
            model.print_trainable_parameters()

    # Load and tokenize data
    if is_main:
        print(f"Loading SFT data from {args.data}...")
    raw_data = load_sft_data(args.data)
    if is_main:
        print(f"  {len(raw_data)} trajectories")

    class SFTDataset(Dataset):
        def __init__(self, data, tokenizer, max_length):
            self.examples = []
            skipped = 0
            n_assistant_tokens = 0
            n_total_tokens = 0
            for item in data:
                input_ids, attention_mask, labels = build_masked_labels(
                    tokenizer, item["messages"], max_length, torch)
                if input_ids.shape[0] < 10:
                    skipped += 1
                    continue
                n_total_tokens += input_ids.shape[0]
                n_assistant_tokens += (labels != -100).sum().item()
                self.examples.append({
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "labels": labels,
                })
            if is_main:
                if skipped:
                    print(f"  Skipped {skipped} too-short examples")
                if n_total_tokens > 0:
                    pct = 100 * n_assistant_tokens / n_total_tokens
                    print(f"  Assistant tokens: {n_assistant_tokens}/"
                          f"{n_total_tokens} ({pct:.1f}% of total)")

        def __len__(self):
            return len(self.examples)

        def __getitem__(self, idx):
            return self.examples[idx]

    dataset = SFTDataset(raw_data, tokenizer, args.max_length)
    if is_main:
        print(f"  {len(dataset)} tokenized examples")

    # Training arguments
    output_dir = Path(args.output)
    extra_args = {}
    if is_distributed:
        extra_args["ddp_find_unused_parameters"] = False
        if args.lora:
            extra_args["fsdp"] = ""  # DDP for LoRA (lighter)
        else:
            extra_args["fsdp"] = "full_shard auto_wrap"

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.1,
        bf16=args.bf16,
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
        print(f"\nStarting SFT training...")
        print(f"  Model: {args.model}")
        print(f"  LoRA: {args.lora} (rank={args.lora_rank})")
        print(f"  GPUs: {n_gpus}")
        print(f"  Epochs: {args.epochs}")
        print(f"  Effective batch: "
              f"{args.batch_size * args.grad_accum * n_gpus}")
        print(f"  LR: {args.lr}")
        print(f"  Output: {output_dir}")

    trainer.train()

    # Save
    if is_main:
        print(f"\nSaving to {output_dir}...")
    trainer.save_model(str(output_dir))
    if is_main:
        tokenizer.save_pretrained(str(output_dir))
        print("Done!")


if __name__ == "__main__":
    main()
