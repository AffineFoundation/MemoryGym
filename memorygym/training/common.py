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


def _find_subseq(seq, subseq, start=0):
    """Find first occurrence of subseq in seq starting at start. Returns -1 if not found."""
    slen = len(subseq)
    for i in range(start, len(seq) - slen + 1):
        if seq[i:i + slen] == subseq:
            return i
    return -1


def build_assistant_mask(tokenizer, input_ids, full_text: str | None = None):
    """Build labels tensor with -100 for non-assistant tokens.

    Only assistant turns contribute to loss — system/user tokens are masked.
    Works with Qwen-style chat templates (<|im_start|>assistant).
    Uses token-id matching instead of repeated re-tokenization for O(n).
    """
    import torch

    labels = torch.full_like(input_ids, -100)
    if full_text is None:
        full_text = tokenizer.decode(input_ids, skip_special_tokens=False)

    marker_start = "<|im_start|>assistant"
    marker_end = "<|im_end|>"

    # Try token-id based approach (fast O(n) scan)
    start_ids = tokenizer.encode(marker_start, add_special_tokens=False)
    end_ids = tokenizer.encode(marker_end, add_special_tokens=False)
    ids = input_ids.tolist()
    n = len(ids)

    pos = 0
    found_any = False
    while pos < n:
        start = _find_subseq(ids, start_ids, pos)
        if start == -1:
            break
        # Content starts after marker + newline token
        content_start = start + len(start_ids)
        # Skip newline token if present
        if content_start < n and tokenizer.decode(
                [ids[content_start]]).strip() == "":
            content_start += 1
        end = _find_subseq(ids, end_ids, content_start)
        if end == -1:
            tok_end = n
        else:
            tok_end = end + len(end_ids)
        labels[content_start:tok_end] = input_ids[content_start:tok_end]
        found_any = True
        pos = tok_end

    if not found_any:
        return input_ids.clone()  # Fallback: train all

    return labels


def count_assistant_turns(tokenizer, input_ids) -> int:
    """Count the number of assistant turns in a tokenized sequence.

    Used by turn-level GRPO to map turn_rewards to token spans.
    """
    marker_ids = tokenizer.encode("<|im_start|>assistant",
                                  add_special_tokens=False)
    ids = input_ids.tolist()
    count = 0
    pos = 0
    mlen = len(marker_ids)
    while pos <= len(ids) - mlen:
        if ids[pos:pos + mlen] == marker_ids:
            count += 1
            pos += mlen
        else:
            pos += 1
    return count


def build_turn_advantage_weights(tokenizer, input_ids, turn_advantages):
    """Build per-token advantage weights from per-turn advantages.

    Returns a tensor of shape (seq_len,) where each assistant token gets
    the advantage of its corresponding turn. Non-assistant tokens get 0.

    Args:
        tokenizer: HF tokenizer
        input_ids: 1D tensor of token ids
        turn_advantages: list of float, one per assistant turn

    Returns:
        Tensor of per-token advantages (shape matches input_ids)
    """
    import torch

    weights = torch.zeros_like(input_ids, dtype=torch.float32)
    marker_start = tokenizer.encode("<|im_start|>assistant",
                                    add_special_tokens=False)
    marker_end = tokenizer.encode("<|im_end|>", add_special_tokens=False)
    ids = input_ids.tolist()
    n = len(ids)

    pos = 0
    turn_idx = 0
    while pos < n and turn_idx < len(turn_advantages):
        start = _find_subseq(ids, marker_start, pos)
        if start == -1:
            break
        content_start = start + len(marker_start)
        if content_start < n and tokenizer.decode(
                [ids[content_start]]).strip() == "":
            content_start += 1
        end = _find_subseq(ids, marker_end, content_start)
        tok_end = end + len(marker_end) if end != -1 else n
        weights[content_start:tok_end] = turn_advantages[turn_idx]
        turn_idx += 1
        pos = tok_end

    return weights


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
