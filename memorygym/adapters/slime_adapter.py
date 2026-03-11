"""slime adapter: custom generate/reward functions for MemoryEnv.

Usage with slime:
    python -m slime.train \
        --custom-generate-function-path memorygym.adapters.slime_adapter.generate \
        --custom-rm-path memorygym.adapters.slime_adapter.reward_func \
        --advantage-estimator grpo \
        --n-samples-per-prompt 8

Data format (JSONL):
    {"prompt": [{"role": "user", "content": "..."}],
     "extra": {"template": "company", "tier": "lite", "seed": 42}}
"""

from __future__ import annotations

import json
import re
from typing import Any

from ._common import (
    format_tool_result,
    get_system_prompt,
    parse_tool_calls,
)
from memorygym.training import MemoryEnv


async def generate(
    args: Any,
    sample: Any,
    sampling_params: Any,
) -> Any:
    """slime custom generate function for multi-turn MemoryEnv episodes.

    Called by slime's rollout worker. Drives the full episode loop:
    model generates → parse tool calls → env.step() → feedback → repeat.

    Args:
        args: slime training args.
        sample: slime Sample object with .prompt, .extra, .output, .loss_mask.
        sampling_params: Generation parameters.

    Returns:
        Modified sample with .output (full response text) and
        .loss_mask (per-token, 1=model 0=env).
    """
    # Extract episode config from sample metadata
    extra = getattr(sample, "extra", {}) or {}
    template_name = extra.get("template", "company")
    tier = extra.get("tier", "lite")
    seed = extra.get("seed", 0)

    env = MemoryEnv(template_name=template_name, tier=tier, seed=seed)
    obs = env.reset(seed=seed)
    system_prompt = get_system_prompt(env.write_budget)

    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": obs},
    ]

    # Collect full output text and per-segment mask labels
    segments: list[tuple[str, int]] = []  # (text, is_model)
    done = False
    max_turns = 200
    turn = 0

    # slime provides a post() function for LLM inference
    post = getattr(args, "post", None)
    if post is None:
        raise ValueError("slime args.post (LLM inference function) not found")

    while not done and turn < max_turns:
        # Model generates via slime's SGLang server
        model_text = await _generate_turn(post, context, sampling_params)
        segments.append((model_text, 1))  # model tokens → loss_mask=1
        context.append({"role": "assistant", "content": model_text})

        # Parse and execute tool calls
        tool_calls = parse_tool_calls(model_text)
        if not tool_calls:
            _, _, done, info = env.step({"tool": "next"})
            if done:
                break
            next_obs = env.current_observation()
            segments.append((next_obs, 0))  # env tokens → loss_mask=0
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
            segments.append((feedback, 0))  # env tokens → loss_mask=0
            context.append({"role": "user", "content": feedback})

        turn += 1

    # Build output and loss_mask for slime
    full_output = "".join(seg[0] for seg in segments)

    # Store reward in sample for reward_func to retrieve
    if not hasattr(sample, "_memorygym_reward"):
        sample._memorygym_reward = env.get_verifiable_reward()
    sample._memorygym_stats = info.get("episode_stats", {}) if info else {}
    env.close()

    # Set output on sample (slime convention)
    sample.output = full_output

    # Build per-character mask, slime's tokenizer converts to per-token
    char_mask = []
    for text, is_model in segments:
        char_mask.extend([is_model] * len(text))
    sample.loss_mask = char_mask

    return sample


async def reward_func(
    args: Any,
    sample: Any,
    **kwargs: Any,
) -> float:
    """slime custom reward function.

    Returns the episode accuracy score computed during generate().
    """
    return getattr(sample, "_memorygym_reward", 0.0)


async def _generate_turn(
    post,
    context: list[dict],
    sampling_params: Any,
) -> str:
    """Call slime's LLM server for one generation turn."""
    payload = {
        "messages": context,
        "max_tokens": getattr(sampling_params, "max_tokens", 2048),
        "temperature": getattr(sampling_params, "temperature", 0.7),
    }
    response = await post(payload)
    # Extract generated text from response
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("text", response.get("content", ""))
    return str(response)
