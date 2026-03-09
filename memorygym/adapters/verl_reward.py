"""verl reward function for MemoryGym.

Used as custom_reward_function in verl config:
    custom_reward_function:
      path: memorygym/adapters/verl_reward.py
      name: compute_score

When using MemoryGymAgentLoop, reward_score is already set
in AgentLoopOutput. This module provides a fallback compute_score
for non-agent-loop setups (e.g., single-turn SFT→GRPO bootstrap).
"""

from __future__ import annotations

from typing import Any


def compute_score(
    data_source: str,
    solution_str: str,
    ground_truth: str,
    extra_info: dict[str, Any] | None = None,
    **kwargs,
) -> float:
    """Compute reward score for MemoryGym trajectories.

    In agent-loop mode, reward is computed by MemoryEnv and set as
    reward_score in AgentLoopOutput — this function is not called.

    In single-turn mode (bootstrap), this evaluates the final answer.
    """
    extra_info = extra_info or {}

    # If reward was pre-computed by agent loop
    if "env_reward" in extra_info:
        return float(extra_info["env_reward"])

    # Single-turn fallback: exact match
    if not solution_str or not ground_truth:
        return 0.0

    solution_clean = solution_str.strip().lower()
    ground_truth_clean = ground_truth.strip().lower()

    if solution_clean == ground_truth_clean:
        return 1.0

    # Numeric comparison with 2% tolerance
    try:
        sol_num = float(solution_clean.replace(",", "").replace("%", ""))
        gt_num = float(ground_truth_clean.replace(",", "").replace("%", ""))
        if gt_num == 0:
            return 1.0 if sol_num == 0 else 0.0
        if abs(sol_num - gt_num) / abs(gt_num) <= 0.02:
            return 1.0
    except ValueError:
        pass

    return 0.0
