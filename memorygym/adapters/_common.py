"""Shared utilities for RL framework adapters.

Tool-call parsing and result formatting shared between verl and slime adapters.
"""

from __future__ import annotations

import json
import re
from typing import Any


_TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)


def parse_tool_calls(text: str) -> list[dict[str, Any]]:
    """Parse <tool_call>...</tool_call> blocks from model output.

    Returns list of {"tool": str, "args": dict}.
    """
    calls = []
    for match in _TOOL_CALL_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
            calls.append({
                "tool": data["name"],
                "args": data.get("arguments", {}),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return calls


def format_tool_result(action: dict[str, Any], info: dict[str, Any]) -> str:
    """Format MemoryEnv step result as text feedback for the model."""
    tool = action["tool"]

    if tool == "memory_store":
        if "error" in info:
            return f"[memory_store] Error: {info['error']}"
        return (
            f"[memory_store] Stored (id={info['memory_id']}). "
            f"Budget remaining: {info['remaining']}"
        )

    if tool == "memory_search":
        results = info.get("results", [])
        if not results:
            return "[memory_search] No results found."
        lines = [f"[memory_search] {len(results)} result(s):"]
        for r in results:
            content_preview = r["content"][:200]
            lines.append(f"  [{r['id']}] {content_preview}")
        return "\n".join(lines)

    if tool == "memory_forget":
        if info.get("deleted"):
            return "[memory_forget] Deleted."
        return "[memory_forget] ID not found."

    if tool == "submit_answer":
        answer = action["args"].get("answer", "")
        return f"[submit_answer] ANSWER_SUBMITTED: {answer}"

    return f"[{tool}] Done."


def get_system_prompt(budget: int) -> str:
    """Get the standard MemoryGym system prompt."""
    from memorygym.agents.stream_agent import SYSTEM_PROMPT
    return SYSTEM_PROMPT.format(budget=budget)


def run_episode(
    env,
    generate_fn,
    tokenize_fn,
    max_turns: int = 200,
) -> dict[str, Any]:
    """Run a complete MemoryEnv episode, collecting tokens and masks.

    Framework-agnostic episode runner. Both verl and slime adapters
    use this to drive the environment loop.

    Args:
        env: MemoryEnv instance (already reset).
        generate_fn: Callable(context: list[dict]) -> str.
            Calls the LLM and returns generated text.
        tokenize_fn: Callable(text: str) -> list[int].
            Tokenizes text to token IDs.
        max_turns: Maximum generation turns per episode.

    Returns:
        {
            "prompt_tokens": list[int],      # initial observation tokens
            "response_tokens": list[int],    # all response tokens (model + env)
            "loss_mask": list[int],          # 1=model, 0=environment
            "reward": float,                 # episode reward
            "stats": dict,                   # episode statistics
        }
    """
    system_prompt = get_system_prompt(env.write_budget)
    first_obs = env._format_event(env._stream[0])

    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": first_obs},
    ]
    prompt_tokens = tokenize_fn(system_prompt + "\n" + first_obs)

    response_tokens: list[int] = []
    loss_mask: list[int] = []
    done = False
    turn = 0

    while not done and turn < max_turns:
        # Model generates
        model_text = generate_fn(context)
        model_tokens = tokenize_fn(model_text)
        response_tokens.extend(model_tokens)
        loss_mask.extend([1] * len(model_tokens))

        context.append({"role": "assistant", "content": model_text})

        # Parse and execute tool calls
        tool_calls = parse_tool_calls(model_text)
        if not tool_calls:
            # No tool call → advance to next event
            _, _, done, info = env.step({"tool": "next"})
            if done:
                break
            obs = env._format_event(env._stream[env._event_idx])
            obs_tokens = tokenize_fn(obs)
            response_tokens.extend(obs_tokens)
            loss_mask.extend([0] * len(obs_tokens))
            context.append({"role": "user", "content": obs})
        else:
            feedback_parts = []
            for action in tool_calls:
                obs, reward, done, info = env.step(action)
                feedback_parts.append(format_tool_result(action, info))
                if done:
                    break

            feedback = "\n".join(feedback_parts)
            if not done:
                feedback += "\n\n" + obs
            feedback_tokens = tokenize_fn(feedback)
            response_tokens.extend(feedback_tokens)
            loss_mask.extend([0] * len(feedback_tokens))
            context.append({"role": "user", "content": feedback})

        turn += 1

    return {
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "loss_mask": loss_mask,
        "reward": env.get_verifiable_reward(),
        "stats": info.get("episode_stats", {}) if info else {},
    }
