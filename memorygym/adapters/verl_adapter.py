"""verl adapter: AgentLoopBase integration for MemoryEnv.

Registers a "memorygym_agent" agent loop for verl's multi-turn training.
MemoryEnv drives the environment; verl's server_manager handles LLM generation.

Usage in verl config YAML:
    actor_rollout_ref:
      rollout:
        agent:
          agent_loop_config_path: scripts/memorygym_agent.yaml

Agent loop config (memorygym_agent.yaml):
    - name: memorygym_agent
      _target_: memorygym.adapters.verl_adapter.MemoryGymAgentLoop
      template_name: company
      tier: lite
      max_env_turns: 200

Data format (JSONL):
    {"prompt": [{"role": "user", "content": "..."}],
     "extra_info": {"template": "company", "tier": "lite", "seed": 42}}
"""

from __future__ import annotations

import logging
import os
from typing import Any
from uuid import uuid4

from ._common import (
    format_tool_result,
    get_system_prompt,
    parse_tool_calls,
)
from memorygym.training import MemoryEnv

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("VERL_LOGGING_LEVEL", "WARN"))

# Import verl components — deferred to avoid hard dependency
try:
    from verl.experimental.agent_loop.agent_loop import (
        AgentLoopBase,
        AgentLoopMetrics,
        AgentLoopOutput,
        AsyncLLMServerManager,
        DictConfigWrap,
        register,
    )

    _VERL_AVAILABLE = True
except ImportError:
    _VERL_AVAILABLE = False


def _check_verl():
    if not _VERL_AVAILABLE:
        raise ImportError(
            "verl is required for MemoryGymAgentLoop. "
            "Install with: pip install verl"
        )


if _VERL_AVAILABLE:

    @register("memorygym_agent")
    class MemoryGymAgentLoop(AgentLoopBase):
        """verl agent loop driving MemoryEnv episodes.

        Each episode: ingest events → model stores selectively →
        corrections → model updates → questions → model answers.
        """

        def __init__(
            self,
            trainer_config: DictConfigWrap,
            server_manager: AsyncLLMServerManager,
            tokenizer,
            processor,
            template_name: str = "company",
            tier: str = "lite",
            max_env_turns: int = 200,
            **kwargs,
        ):
            super().__init__(
                trainer_config, server_manager, tokenizer, processor,
                **kwargs,
            )
            self.template_name = template_name
            self.tier = tier
            self.max_env_turns = max_env_turns
            config = trainer_config.config
            self.response_length = (
                config.actor_rollout_ref.rollout.response_length
            )

        async def run(
            self,
            sampling_params: dict[str, Any],
            **kwargs,
        ) -> AgentLoopOutput:
            """Run one MemoryEnv episode.

            kwargs["raw_prompt"]: initial messages from dataset
            kwargs["extra_info"]: {"template", "tier", "seed"}
            """
            raw_prompt = list(kwargs.get("raw_prompt", []))
            extra_info = kwargs.get("extra_info", {})

            # Episode config from data or defaults
            template = extra_info.get("template", self.template_name)
            tier = extra_info.get("tier", self.tier)
            seed = extra_info.get("seed", 0)

            # Set up environment
            env = MemoryEnv(template_name=template, tier=tier, seed=seed)
            obs = env.reset(seed=seed)
            system_prompt = get_system_prompt(env.write_budget)

            # Build initial messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": obs},
            ]

            # Tokenize prompt
            prompt_ids = await self.apply_chat_template(messages)

            # Tracking
            all_ids = list(prompt_ids)  # accumulates prompt + response
            response_mask: list[int] = []
            response_logprobs: list[float] = []
            metrics: dict[str, float] = {}
            request_id = uuid4().hex
            n_generate = 0
            n_tool_calls = 0

            done = False
            turn = 0

            while not done and turn < self.max_env_turns:
                # Check length limit
                if len(response_mask) >= self.response_length:
                    break

                # Generate via verl's LLM server
                output = await self.server_manager.generate(
                    request_id=request_id,
                    prompt_ids=all_ids,
                    sampling_params=sampling_params,
                )
                n_generate += 1

                # Model tokens → mask=1
                model_token_ids = output.token_ids
                all_ids.extend(model_token_ids)
                response_mask.extend([1] * len(model_token_ids))
                if output.log_probs:
                    response_logprobs.extend(output.log_probs)

                # Decode model output to get tool calls
                model_text = await self.loop.run_in_executor(
                    None,
                    lambda: self.tokenizer.decode(
                        model_token_ids, skip_special_tokens=True,
                    ),
                )

                # Parse and execute tool calls
                tool_calls = parse_tool_calls(model_text)

                if not tool_calls:
                    # No tool call → advance env
                    _, _, done, info = env.step({"tool": "next"})
                    if done:
                        break
                    env_text = env.current_observation()
                else:
                    # Execute each tool call
                    feedback_parts = []
                    for action in tool_calls:
                        obs_text, _, done, info = env.step(action)
                        feedback_parts.append(
                            format_tool_result(action, info),
                        )
                        n_tool_calls += 1
                        if done:
                            break

                    env_text = "\n".join(feedback_parts)
                    if not done:
                        env_text += "\n\n" + obs_text

                if done:
                    break

                # Tokenize environment feedback → mask=0
                messages.append(
                    {"role": "assistant", "content": model_text},
                )
                messages.append({"role": "user", "content": env_text})
                env_ids = await self.apply_chat_template(messages)
                # Only new tokens from env feedback
                new_env_ids = env_ids[len(all_ids):]
                all_ids.extend(new_env_ids)
                response_mask.extend([0] * len(new_env_ids))

                turn += 1

            # Build output
            response_ids = all_ids[len(prompt_ids):]
            # Truncate to response_length
            response_ids = response_ids[: self.response_length]
            response_mask = response_mask[: self.response_length]

            metrics["generate_sequences"] = float(n_generate)
            metrics["tool_calls"] = float(n_tool_calls)

            reward = env.get_verifiable_reward()
            stats = info.get("episode_stats", {}) if info else {}

            return AgentLoopOutput(
                prompt_ids=prompt_ids,
                response_ids=response_ids,
                response_mask=response_mask,
                response_logprobs=(
                    response_logprobs[: self.response_length]
                    if response_logprobs
                    else None
                ),
                reward_score=reward,
                num_turns=turn * 2 + 1,
                metrics=AgentLoopMetrics(**metrics),
                extra_fields={
                    "episode_stats": stats,
                    "env_reward": reward,
                },
            )

else:
    # Fallback when verl not installed — for testing only
    class MemoryGymAgentLoop:  # type: ignore[no-redef]
        """Stub when verl is not installed."""

        def __init__(self, **kwargs):
            _check_verl()
