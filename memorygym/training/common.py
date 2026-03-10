"""Shared training utilities: model loading, masking, generation helpers.

Used by both SFT and GRPO training pipelines. GPU-dependent imports
are deferred (inside functions) to keep env.py CPU-only.
"""

from __future__ import annotations

import inspect
import os
import re
from typing import Any


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from model output."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)


def strip_special_tokens(text: str) -> str:
    """Remove common special tokens from decoded text."""
    for tag in ("<|im_end|>", "<|endoftext|>", "<|im_start|>"):
        text = text.replace(tag, "")
    return text.strip()


def get_chat_kwargs(tokenizer) -> dict:
    """Detect Qwen3 thinking mode and return disable kwargs."""
    try:
        sig = inspect.signature(tokenizer.apply_chat_template)
        if "enable_thinking" in sig.parameters:
            return {"enable_thinking": False}
    except (TypeError, ValueError):
        pass
    return {}


def apply_chat_template(tokenizer, messages: list[dict],
                        chat_kwargs: dict | None = None) -> str:
    """Apply chat template with fallback for models without kwargs."""
    kwargs = chat_kwargs or {}
    try:
        return tokenizer.apply_chat_template(
            messages, tokenize=False, **kwargs)
    except TypeError:
        return tokenizer.apply_chat_template(
            messages, tokenize=False)


def build_assistant_mask(tokenizer, input_ids, full_text: str | None = None):
    """Build labels tensor with -100 for non-assistant tokens.

    Only assistant turns contribute to loss — system/user tokens are masked.
    Works with Qwen-style chat templates (<|im_start|>assistant).
    """
    import torch

    labels = torch.full_like(input_ids, -100)
    if full_text is None:
        full_text = tokenizer.decode(input_ids, skip_special_tokens=False)

    marker_start = "<|im_start|>assistant"
    marker_end = "<|im_end|>"
    pos = 0
    spans = []
    while True:
        start = full_text.find(marker_start, pos)
        if start == -1:
            break
        content_start = full_text.find("\n", start) + 1
        end = full_text.find(marker_end, content_start)
        if end == -1:
            end = len(full_text)
        end += len(marker_end)
        spans.append((content_start, end))
        pos = end

    if not spans:
        return input_ids.clone()  # Fallback: train all

    for char_start, char_end in spans:
        prefix_toks = tokenizer(
            full_text[:char_start], add_special_tokens=False,
            return_tensors="pt")["input_ids"]
        tok_start = prefix_toks.shape[1]
        prefix_plus = tokenizer(
            full_text[:char_end], add_special_tokens=False,
            return_tensors="pt")["input_ids"]
        tok_end = min(prefix_plus.shape[1], len(input_ids))
        labels[tok_start:tok_end] = input_ids[tok_start:tok_end]

    return labels


def load_model(
    model_path: str,
    adapter_path: str | None = None,
    lora_rank: int | None = None,
    bf16: bool = True,
    distributed: bool = False,
    merge_adapter: bool = True,
) -> tuple[Any, Any]:
    """Load model + tokenizer with optional adapter and new LoRA.

    Returns (model, tokenizer).

    Args:
        model_path: HuggingFace model path or local dir.
        adapter_path: LoRA adapter to load and optionally merge.
        lora_rank: If set, add a fresh trainable LoRA layer.
        bf16: Use bfloat16.
        distributed: If True, skip device_map="auto" for DDP/FSDP.
        merge_adapter: If True, merge adapter before applying new LoRA.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict[str, Any] = {
        "dtype": torch.bfloat16 if bf16 else torch.float32,
        "trust_remote_code": True,
    }
    if not distributed:
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs)

    if adapter_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter_path)
        if merge_adapter:
            model = model.merge_and_unload()

    if lora_rank:
        from peft import LoraConfig, get_peft_model
        config = LoraConfig(
            r=lora_rank,
            lora_alpha=lora_rank * 2,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.0,
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, config)

    return model, tokenizer


def ensure_offline():
    """Set HF offline env vars to prevent network hangs."""
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
