"""Tests for RL framework adapter shared utilities."""

from memorygym.adapters._common import (
    format_tool_result,
    parse_tool_calls,
    get_system_prompt,
    run_episode,
)
from memorygym.training import MemoryEnv


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
        assert "mem_001" in result
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
        assert "memory_store" in prompt


class TestRunEpisode:
    def test_episode_completes(self):
        env = MemoryEnv(template_name="company", tier="lite", seed=0)
        env.reset(seed=0)

        turn_count = 0

        def fake_generate(context):
            nonlocal turn_count
            turn_count += 1
            event = env._stream[env._event_idx]
            if event["type"] == "question":
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
            event = env._stream[env._event_idx]
            if event["type"] == "question":
                return '<tool_call>{"name": "submit_answer", "arguments": {"answer": "N/A"}}</tool_call>'
            # Store something on first ingest
            if event["type"] == "ingest":
                return '<tool_call>{"name": "memory_store", "arguments": {"content": "test data"}}</tool_call>'
            return ""

        def fake_tokenize(text):
            return [0] * max(1, len(text) // 4)

        result = run_episode(env, fake_generate, fake_tokenize, max_turns=500)

        # Should have both model tokens (1) and env tokens (0)
        assert 1 in result["loss_mask"]
        assert 0 in result["loss_mask"]
