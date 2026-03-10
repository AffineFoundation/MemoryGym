"""Tests for RL framework adapter shared utilities."""

import importlib
import sys
from pathlib import Path

import pytest

from memorygym.adapters._common import (
    format_tool_result,
    parse_tool_calls,
    get_system_prompt,
    run_episode,
)
from memorygym.adapters.verl_reward import compute_score
from memorygym.training import MemoryEnv


def _verl_importable() -> bool:
    """Check if verl's full import chain works."""
    try:
        from verl.experimental.agent_loop.agent_loop import AgentLoopBase
        return True
    except (ImportError, Exception):
        return False


class TestParseToolCalls:
    def test_single_call(self):
        text = '<tool_call>{"name": "memory_store", "arguments": {"content": "test"}}</tool_call>'
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "memory_store"
        assert calls[0]["args"]["content"] == "test"

    def test_multiple_calls(self):
        text = (
            '<tool_call>{"name": "memory_search", "arguments": {"query": "foo"}}</tool_call>\n'
            '<tool_call>{"name": "memory_store", "arguments": {"content": "bar"}}</tool_call>'
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["tool"] == "memory_search"
        assert calls[1]["tool"] == "memory_store"

    def test_no_calls(self):
        assert parse_tool_calls("just some text") == []

    def test_malformed_json_skipped(self):
        text = '<tool_call>not valid json</tool_call>'
        assert parse_tool_calls(text) == []

    def test_mixed_valid_invalid(self):
        text = (
            '<tool_call>broken</tool_call>\n'
            '<tool_call>{"name": "memory_store", "arguments": {"content": "ok"}}</tool_call>'
        )
        calls = parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "memory_store"

    def test_submit_answer(self):
        text = '<tool_call>{"name": "submit_answer", "arguments": {"answer": "42"}}</tool_call>'
        calls = parse_tool_calls(text)
        assert calls[0]["tool"] == "submit_answer"
        assert calls[0]["args"]["answer"] == "42"


class TestFormatToolResult:
    def test_store_success(self):
        result = format_tool_result(
            {"tool": "memory_store", "args": {"content": "x"}},
            {"memory_id": "mem_001", "remaining": 14},
        )
        assert "Stored" in result
        assert "14" in result

    def test_store_budget_exhausted(self):
        result = format_tool_result(
            {"tool": "memory_store", "args": {"content": "x"}},
            {"error": "Budget exhausted"},
        )
        assert "Error" in result

    def test_search_no_results(self):
        result = format_tool_result(
            {"tool": "memory_search", "args": {"query": "q"}},
            {"results": []},
        )
        assert "No results" in result

    def test_search_with_results(self):
        result = format_tool_result(
            {"tool": "memory_search", "args": {"query": "q"}},
            {"results": [{"id": "mem_001", "content": "some data"}]},
        )
        assert "1 result" in result
        assert "mem_001" in result

    def test_forget_success(self):
        result = format_tool_result(
            {"tool": "memory_forget", "args": {"memory_id": "mem_001"}},
            {"deleted": True},
        )
        assert "Deleted" in result

    def test_forget_not_found(self):
        result = format_tool_result(
            {"tool": "memory_forget", "args": {"memory_id": "xxx"}},
            {"deleted": False},
        )
        assert "not found" in result

    def test_submit_answer(self):
        result = format_tool_result(
            {"tool": "submit_answer", "args": {"answer": "42"}},
            {},
        )
        assert "ANSWER_SUBMITTED" in result


class TestGetSystemPrompt:
    def test_contains_budget(self):
        prompt = get_system_prompt(15)
        assert "15" in prompt
        assert "Write" in prompt


class TestRunEpisode:
    def test_episode_completes(self):
        env = MemoryEnv(template_name="company", tier="lite", seed=0)
        env.reset(seed=0)

        turn_count = 0

        def fake_generate(context):
            nonlocal turn_count
            turn_count += 1
            obs = env.current_observation()
            if "QUESTION" in obs:
                return '<tool_call>{"name": "submit_answer", "arguments": {"answer": "I don\'t know"}}</tool_call>'
            return ""  # no tool call → advance

        def fake_tokenize(text):
            return list(range(len(text) // 4 + 1))

        result = run_episode(env, fake_generate, fake_tokenize, max_turns=500)

        assert "reward" in result
        assert "prompt_tokens" in result
        assert "response_tokens" in result
        assert "loss_mask" in result
        assert len(result["response_tokens"]) == len(result["loss_mask"])
        assert result["reward"] >= 0.0

    def test_loss_mask_has_both_values(self):
        env = MemoryEnv(template_name="company", tier="lite", seed=0)
        env.reset(seed=0)

        def fake_generate(context):
            obs = env.current_observation()
            if "QUESTION" in obs:
                return '<tool_call>{"name": "submit_answer", "arguments": {"answer": "N/A"}}</tool_call>'
            if "DOCUMENTS" in obs:
                return '<tool_call>{"name": "memory_store", "arguments": {"content": "test data"}}</tool_call>'
            return ""

        def fake_tokenize(text):
            return [0] * max(1, len(text) // 4)

        result = run_episode(env, fake_generate, fake_tokenize, max_turns=500)

        # Should have both model tokens (1) and env tokens (0)
        assert 1 in result["loss_mask"]
        assert 0 in result["loss_mask"]


class TestVerlReward:
    def test_exact_match(self):
        assert compute_score("memorygym", "42", "42") == 1.0

    def test_case_insensitive(self):
        assert compute_score("memorygym", "Alice", "alice") == 1.0

    def test_mismatch(self):
        assert compute_score("memorygym", "43", "42") == 0.0

    def test_numeric_tolerance(self):
        # 2% tolerance: 100 vs 101 → within tolerance
        assert compute_score("memorygym", "101", "100") == 1.0
        # 5% → outside tolerance
        assert compute_score("memorygym", "105", "100") == 0.0

    def test_empty_strings(self):
        assert compute_score("memorygym", "", "42") == 0.0
        assert compute_score("memorygym", "42", "") == 0.0

    def test_pre_computed_reward(self):
        score = compute_score(
            "memorygym", "", "",
            extra_info={"env_reward": 0.75},
        )
        assert score == 0.75

    def test_percentage_format(self):
        assert compute_score("memorygym", "50%", "50%") == 1.0


class TestVerlAdapterImport:
    def test_verl_adapter_importable(self):
        """Verify verl adapter module loads without error."""
        from memorygym.adapters import verl_adapter
        assert hasattr(verl_adapter, "MemoryGymAgentLoop")

    def test_verl_available_detected(self):
        """_VERL_AVAILABLE depends on full verl import chain."""
        from memorygym.adapters import verl_adapter
        # May be False if transformers version incompatible
        assert isinstance(verl_adapter._VERL_AVAILABLE, bool)

    @pytest.mark.skipif(
        not _verl_importable(),
        reason="verl import chain requires compatible transformers",
    )
    def test_agent_registered(self):
        """Verify the agent loop is registered with verl."""
        from verl.experimental.agent_loop.agent_loop import (
            _agent_loop_registry,
        )
        assert "memorygym_agent" in _agent_loop_registry


class TestSlimeAdapter:
    def test_generate_signature(self):
        """slime generate() has correct async signature."""
        import inspect
        from memorygym.adapters.slime_adapter import generate
        sig = inspect.signature(generate)
        params = list(sig.parameters.keys())
        assert "args" in params
        assert "sample" in params
        assert "sampling_params" in params
        assert inspect.iscoroutinefunction(generate)

    def test_reward_func_signature(self):
        """slime reward_func() has correct async signature."""
        import inspect
        from memorygym.adapters.slime_adapter import reward_func
        sig = inspect.signature(reward_func)
        assert "args" in list(sig.parameters.keys())
        assert "sample" in list(sig.parameters.keys())
        assert inspect.iscoroutinefunction(reward_func)

    def test_reward_func_returns_stored_reward(self):
        """reward_func returns _memorygym_reward from sample."""
        import asyncio
        from memorygym.adapters.slime_adapter import reward_func

        class FakeSample:
            _memorygym_reward = 0.42

        sample = FakeSample()
        result = asyncio.new_event_loop().run_until_complete(
            reward_func(None, sample))
        assert result == 0.42

    def test_reward_func_default_zero(self):
        """reward_func returns 0.0 when no reward stored."""
        import asyncio
        from memorygym.adapters.slime_adapter import reward_func

        class EmptySample:
            pass

        result = asyncio.new_event_loop().run_until_complete(
            reward_func(None, EmptySample()))
        assert result == 0.0


class TestCurrentObservation:
    def test_returns_first_event(self):
        env = MemoryEnv(template_name="company", tier="lite", seed=0)
        env.reset(seed=0)
        obs = env.current_observation()
        assert "DOCUMENTS" in obs or "Event" in obs

    def test_returns_empty_after_done(self):
        env = MemoryEnv(template_name="company", seed=0,
                        n_entities=10, n_questions=3)
        env.reset()
        # Run to completion
        for _ in range(500):
            obs = env.current_observation()
            if not obs:
                break
            if "QUESTION" in obs:
                env.step({"tool": "submit_answer",
                          "args": {"answer": "N/A"}})
            else:
                env.step({"tool": "next"})
        assert env.current_observation() == ""


class TestGenerateTrainData:
    def test_generate_prompts(self):
        # Import from scripts/ directory
        spec = importlib.util.spec_from_file_location(
            "generate_train_data",
            Path(__file__).parent.parent / "scripts" / "generate_train_data.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        prompts = mod.generate_prompts(
            templates=["company"],
            tier="lite",
            seeds=2,
        )
        assert len(prompts) == 2
        for p in prompts:
            assert "prompt" in p
            assert "extra_info" in p
            assert p["extra_info"]["template"] == "company"
            assert p["extra_info"]["tier"] == "lite"
            assert len(p["prompt"]) == 2  # system + user
            assert p["prompt"][0]["role"] == "system"
            assert p["prompt"][1]["role"] == "user"
