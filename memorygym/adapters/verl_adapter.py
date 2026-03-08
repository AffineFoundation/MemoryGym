"""verl adapter: AgentLoopBase integration for MemoryEnv.

Usage with verl config:
    actor_rollout_ref:
      rollout:
        multi_turn: True
        mode: async
    data:
      return_raw_chat: True

    # In your training script:
    from memorygym.adapters.verl_adapter import MemoryGymAgentLoop
    agent_loop = MemoryGymAgentLoop(template_name="company", tier="lite")
"""

from __future__ import annotations

from typing import Any

from memorygym.adapters._common import (
    format_tool_result,
    get_system_prompt,
    parse_tool_calls,
)
from memorygym.training import MemoryEnv


class MemoryGymAgentLoop:
    """verl-compatible agent loop wrapping MemoryEnv.

    Implements the interface expected by verl's AgentLoopBase:
      async run(sampling_params, **kwargs) -> AgentLoopOutput

    The actual AgentLoopBase import is deferred to avoid hard dependency
    on verl. When used with verl, subclass AgentLoopBase instead:

        from verl.workers.agent import AgentLoopBase, AgentLoopOutput
        class Loop(AgentLoopBase, MemoryGymAgentLoop): ...
    """

    def __init__(
        self,
        template_name: str = "company",
        tier: str = "lite",
        max_turns: int = 200,
    ):
        self.template_name = template_name
        self.tier = tier
        self.max_turns = max_turns

    async def run(
        self,
        sampling_params: Any,
        seed: int = 0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run one MemoryEnv episode as a verl agent loop.

        Args:
            sampling_params: verl SamplingParams for LLM generation.
            seed: Episode seed for deterministic world generation.

        Returns:
            Dict with keys matching AgentLoopOutput:
            - prompt_ids: list[int]
            - response_ids: list[int]
            - response_mask: list[int] (1=model, 0=environment)
            - reward: float
        """
        env = MemoryEnv(
            template_name=self.template_name,
            tier=self.tier,
            seed=seed,
        )
        obs = env.reset(seed=seed)
        system_prompt = get_system_prompt(env.write_budget)

        # Tokenizer from kwargs (verl passes it)
        tokenizer = kwargs.get("tokenizer")
        if tokenizer is None:
            raise ValueError("tokenizer must be provided via kwargs")

        def tokenize(text: str) -> list[int]:
            return tokenizer.encode(text, add_special_tokens=False)

        prompt_ids = tokenize(system_prompt + "\n" + obs)
        response_ids: list[int] = []
        response_mask: list[int] = []

        # LLM generate function (verl passes server manager)
        llm = kwargs.get("llm")
        if llm is None:
            raise ValueError("llm server must be provided via kwargs")

        context = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": obs},
        ]

        done = False
        turn = 0

        while not done and turn < self.max_turns:
            # Generate via verl's LLM server
            model_text = await llm.generate(context, sampling_params)
            model_tokens = tokenize(model_text)
            response_ids.extend(model_tokens)
            response_mask.extend([1] * len(model_tokens))
            context.append({"role": "assistant", "content": model_text})

            # Parse and execute actions
            tool_calls = parse_tool_calls(model_text)
            if not tool_calls:
                _, _, done, info = env.step({"tool": "next"})
                if done:
                    break
                next_obs = env._format_event(env._stream[env._event_idx])
                obs_tokens = tokenize(next_obs)
                response_ids.extend(obs_tokens)
                response_mask.extend([0] * len(obs_tokens))
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
                fb_tokens = tokenize(feedback)
                response_ids.extend(fb_tokens)
                response_mask.extend([0] * len(fb_tokens))
                context.append({"role": "user", "content": feedback})

            turn += 1

        return {
            "prompt_ids": prompt_ids,
            "response_ids": response_ids,
            "response_mask": response_mask,
            "reward": env.get_verifiable_reward(),
        }
