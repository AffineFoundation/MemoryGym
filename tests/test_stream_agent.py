"""Tests for stream_agent tool parsing and execution (no API calls)."""

import os

from memorygym.agents.stream_agent import (
    _execute_tool,
    _extract_tool_calls,
    _format_documents,
    _completion_max_tokens,
    _shrink_completion_cap,
    SYSTEM_PROMPT,
    _TOOL_CALL_RE,
)
from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.memory.budget import MemoryBudget


def _parse_and_execute(text, backend, budget):
    """Test helper: parse tool calls and execute, return (results, answer, writes, searches)."""
    results = []
    answer = None
    writes_before = budget.writes_used
    n_searches = 0
    for call in _extract_tool_calls(text):
        name = call.get("name", "")
        args = call.get("arguments", {})
        result_text, submitted = _execute_tool(name, args, backend, budget)
        results.append(f"[{name}] {result_text}")
        if submitted is not None:
            answer = submitted
        if name in ("memory_search", "memory_list", "memory_get", "Read"):
            n_searches += 1
    n_writes = budget.writes_used - writes_before
    return results, answer, n_writes, n_searches


def _fresh_backend():
    """Create a fresh ChromaDB backend for each test."""
    import uuid
    return ChromaDBBackend(collection_name=f"test_{uuid.uuid4().hex[:8]}")


def test_tool_call_regex():
    """Regex extracts JSON from <tool_call> blocks."""
    text = 'I will store this.\n<tool_call>{"name": "memory_store", "arguments": {"content": "test data"}}</tool_call>'
    matches = _TOOL_CALL_RE.findall(text)
    assert len(matches) == 1
    assert '"memory_store"' in matches[0]


def test_tool_call_regex_multiline():
    """Regex works with multiline JSON."""
    text = '<tool_call>\n{"name": "memory_store",\n "arguments": {"content": "multi\\nline"}}\n</tool_call>'
    matches = _TOOL_CALL_RE.findall(text)
    assert len(matches) == 1


def test_tool_call_regex_multiple():
    """Regex extracts multiple tool calls."""
    text = (
        '<tool_call>{"name": "memory_search", "arguments": {"query": "foo"}}</tool_call>\n'
        'Some text\n'
        '<tool_call>{"name": "submit_answer", "arguments": {"answer": "bar"}}</tool_call>'
    )
    matches = _TOOL_CALL_RE.findall(text)
    assert len(matches) == 2


def test_execute_store():
    """memory_store creates an entry and consumes budget."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    result, answer = _execute_tool(
        "memory_store", {"content": "Alice | salary: 100k"}, backend, budget)
    assert "Stored" in result
    assert "4 writes left" in result
    assert answer is None
    assert budget.writes_used == 1
    assert len(backend.list()) == 1


def test_execute_store_budget_exhausted():
    """memory_store fails when budget is exhausted."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=1, writes_used=1)
    result, answer = _execute_tool(
        "memory_store", {"content": "data"}, backend, budget)
    assert "exhausted" in result.lower() or "Budget" in result
    assert answer is None
    assert len(backend.list()) == 0


def test_execute_search():
    """memory_search returns matching entries."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    backend.store("Alice | salary: 100k")
    backend.store("Bob | salary: 200k")
    result, answer = _execute_tool(
        "memory_search", {"query": "Alice"}, backend, budget)
    assert "Alice" in result
    assert answer is None


def test_execute_search_empty():
    """memory_search returns no results message."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    result, answer = _execute_tool(
        "memory_search", {"query": "nonexistent"}, backend, budget)
    assert "No results" in result


def test_execute_forget():
    """memory_forget deletes an entry."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    entry_id = backend.store("Alice | salary: 100k")
    result, answer = _execute_tool(
        "memory_forget", {"memory_id": entry_id}, backend, budget)
    assert "Deleted" in result
    assert len(backend.list()) == 0


def test_execute_list():
    """memory_list returns all entries."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    backend.store("Alice | salary: 100k")
    backend.store("Bob | salary: 200k")
    result, answer = _execute_tool(
        "memory_list", {}, backend, budget)
    assert "Alice" in result
    assert "Bob" in result


def test_execute_submit_answer():
    """submit_answer returns the answer."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    result, answer = _execute_tool(
        "submit_answer", {"answer": "42"}, backend, budget)
    assert answer == "42"
    assert "ANSWER_SUBMITTED" in result


def test_parse_and_execute_store_then_answer():
    """Full parse+execute: store data, then submit answer."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)

    text = (
        '<tool_call>{"name": "memory_store", "arguments": {"content": "Alice | salary: 100k"}}</tool_call>\n'
        '<tool_call>{"name": "submit_answer", "arguments": {"answer": "100k"}}</tool_call>'
    )
    results, answer, n_writes, n_searches = _parse_and_execute(text, backend, budget)
    assert len(results) == 2
    assert answer == "100k"
    assert n_writes == 1
    assert n_searches == 0
    assert budget.writes_used == 1


def test_parse_and_execute_search_then_answer():
    """Parse+execute: search, then answer."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    backend.store("Alice | salary: 100k")

    text = (
        '<tool_call>{"name": "memory_search", "arguments": {"query": "Alice"}}</tool_call>\n'
        '<tool_call>{"name": "submit_answer", "arguments": {"answer": "100k"}}</tool_call>'
    )
    results, answer, n_writes, n_searches = _parse_and_execute(text, backend, budget)
    assert answer == "100k"
    assert n_writes == 0
    assert n_searches == 1


def test_parse_invalid_json_skipped():
    """Invalid JSON in tool_call is silently skipped."""
    backend = _fresh_backend()
    budget = MemoryBudget()
    text = '<tool_call>{invalid json}</tool_call>'
    results, answer, n_w, n_s = _parse_and_execute(text, backend, budget)
    assert len(results) == 0
    assert answer is None


def test_format_documents():
    """Documents are formatted with indices."""
    docs = ["Doc A content", "Doc B content"]
    formatted = _format_documents(docs)
    assert "[Document 1]" in formatted
    assert "[Document 2]" in formatted
    assert "Doc A content" in formatted


def test_system_prompt_budget():
    """System prompt formats budget correctly."""
    prompt = SYSTEM_PROMPT.format(budget=30)
    assert "30" in prompt
    assert "Write" in prompt
    assert "submit_answer" in prompt


def test_completion_max_tokens_default_and_override():
    """Eval max_tokens uses a safe default and respects env override."""
    prev = os.environ.get("MEMORYGYM_MAX_TOKENS")
    try:
        os.environ.pop("MEMORYGYM_MAX_TOKENS", None)
        assert _completion_max_tokens() == 2048
        os.environ["MEMORYGYM_MAX_TOKENS"] = "1024"
        assert _completion_max_tokens() == 1024
        os.environ["MEMORYGYM_MAX_TOKENS"] = "invalid"
        assert _completion_max_tokens() == 2048
    finally:
        if prev is None:
            os.environ.pop("MEMORYGYM_MAX_TOKENS", None)
        else:
            os.environ["MEMORYGYM_MAX_TOKENS"] = prev


def test_shrink_completion_cap_from_overflow_error():
    """Overflow errors should shrink max_tokens based on prompt length."""
    err = (
        "This model's maximum context length is 8192 tokens. "
        "However, you requested 1024 output tokens and your prompt contains "
        "at least 7169 input tokens, for a total of at least 8193 tokens."
    )
    assert _shrink_completion_cap(1024, err) == 959
    assert _shrink_completion_cap(512, "input_tokens, value=8100") == 64
    assert _shrink_completion_cap(64, err) is None


def test_edit_updates_existing():
    """Edit tool updates existing content in memory."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    _execute_tool("Write", {"content": "Alice | salary: 100k"}, backend, budget)
    result, answer = _execute_tool(
        "Edit",
        {"old_text": "salary: 100k", "new_text": "salary: 120k"},
        backend, budget,
    )
    assert "Edited" in result
    entries = backend.list()
    assert any("120k" in e["content"] for e in entries)


def test_content_character_limit():
    """memory_store rejects content exceeding 2000 character limit."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    long_content = "x" * 2001
    result, answer = _execute_tool(
        "memory_store", {"content": long_content}, backend, budget)
    assert "exceeds" in result.lower() or "limit" in result.lower()
    assert budget.writes_used == 0


def test_content_within_character_limit():
    """memory_store accepts content within 2000 character limit."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    content = "x" * 2000
    result, answer = _execute_tool(
        "memory_store", {"content": content}, backend, budget)
    assert "Stored" in result
    assert budget.writes_used == 1


def test_nuclear_redaction_message_count():
    """After N events, messages should always be exactly 3 (system + 1 pair)."""
    # Simulate the redaction logic from run_stream_agent
    messages = [{"role": "system", "content": "system prompt"}]

    for event_idx in range(20):
        # Simulate adding event messages
        messages.append({"role": "user", "content": f"Event {event_idx}"})
        messages.append({"role": "assistant", "content": "Processing..."})

        # Nuclear redaction: keep only system prompt + 1 placeholder pair
        del messages[1:]
        messages.append({"role": "user", "content": f"[{event_idx+1}/20 done]"})
        messages.append({"role": "assistant", "content": "OK."})

        assert len(messages) == 3, f"After event {event_idx}, messages={len(messages)}"


def test_bare_json_tool_calls():
    """Bare JSON (Qwen-style) tool calls are parsed correctly."""
    text = '{"name": "memory_store", "arguments": {"content": "Alice revenue=500"}}\n{"name": "submit_answer", "arguments": {"answer": "500"}}'
    calls = _extract_tool_calls(text)
    assert len(calls) == 2
    assert calls[0]["name"] == "memory_store"
    assert calls[1]["name"] == "submit_answer"


def test_bare_json_parse_and_execute():
    """Full parse+execute with bare JSON format."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    text = '{"name": "memory_store", "arguments": {"content": "Alice | salary: 100k"}}\n{"name": "submit_answer", "arguments": {"answer": "100k"}}'
    results, answer, n_writes, n_searches = _parse_and_execute(text, backend, budget)
    assert len(results) == 2
    assert answer == "100k"
    assert n_writes == 1
    assert budget.writes_used == 1


def test_xml_preferred_over_bare_json():
    """When XML tool_call tags are present, bare JSON is ignored."""
    text = (
        '<tool_call>{"name": "submit_answer", "arguments": {"answer": "from_xml"}}</tool_call>\n'
        '{"name": "submit_answer", "arguments": {"answer": "from_bare"}}'
    )
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["arguments"]["answer"] == "from_xml"


def test_bare_json_ignores_unknown_tools():
    """Bare JSON with unknown tool names is ignored."""
    text = '{"name": "unknown_tool", "arguments": {"data": "test"}}'
    calls = _extract_tool_calls(text)
    assert len(calls) == 0


def test_function_call_tag():
    """<function_call> tag variant is parsed correctly."""
    text = '<function_call>{"name": "memory_store", "arguments": {"content": "test data"}}</function_call>'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "memory_store"


def test_markdown_code_block():
    """Markdown code block format is parsed correctly."""
    text = 'Let me search for that.\n```json\n{"name": "memory_search", "arguments": {"query": "Alice"}}\n```'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "memory_search"


def test_markdown_code_block_no_lang():
    """Markdown code block without language tag works."""
    text = '```\n{"name": "submit_answer", "arguments": {"answer": "42"}}\n```'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "submit_answer"


def test_xml_preferred_over_code_block():
    """XML tool_call tags take priority over code blocks."""
    text = (
        '<tool_call>{"name": "submit_answer", "arguments": {"answer": "from_xml"}}</tool_call>\n'
        '```json\n{"name": "submit_answer", "arguments": {"answer": "from_block"}}\n```'
    )
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["arguments"]["answer"] == "from_xml"


def test_missing_closing_brace_xml():
    """LLM outputs JSON with missing closing brace — should be auto-fixed."""
    # Real failure pattern from MiniMax model evaluations
    text = '<tool_call>{"name": "submit_answer", "arguments": {"answer": "42"}</tool_call>'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "submit_answer"
    assert calls[0]["arguments"]["answer"] == "42"


def test_missing_closing_brace_with_special_chars():
    """Missing brace with apostrophe in value (common failure case)."""
    text = '<tool_call>{"name": "submit_answer", "arguments": {"answer": "I don\'t know"}</tool_call>'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["arguments"]["answer"] == "I don't know"


def test_missing_closing_brace_memory_search():
    """Missing brace on memory_search tool call."""
    text = '<tool_call>{"name": "memory_search", "arguments": {"query": "Entity A"}</tool_call>'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "memory_search"


def test_valid_json_not_broken_by_brace_fix():
    """Valid JSON still works (regression check — don't double-close)."""
    text = '<tool_call>{"name": "Write", "arguments": {"content": "data"}}</tool_call>'
    calls = _extract_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["arguments"]["content"] == "data"


def _check_correction_tracking(turns, new_val):
    """Replicate correction tracking logic from stream_agent for testing."""
    did_store = False
    did_edit = False
    stored_new = False
    for t in turns:
        calls = t.get("tool_calls", [])
        results = t.get("tool_results", [])
        for i, c in enumerate(calls):
            cname = c.get("name", "")
            cargs = c.get("arguments", {})
            result = results[i] if i < len(results) else ""
            if cname in ("Write", "memory_store"):
                if "Budget exhausted" not in result:
                    did_store = True
                    if str(new_val) in str(cargs.get("content", "")):
                        stored_new = True
            elif cname == "Edit":
                if "Edited." in result:
                    did_edit = True
                    if str(new_val) in str(cargs.get("new_text", "")):
                        stored_new = True
    return (did_store or did_edit) and stored_new


def test_correction_tracker_edit_success():
    """Correction tracker reports success when Edit succeeds."""
    turns = [{
        "tool_calls": [
            {"name": "memory_search", "arguments": {"query": "Alice"}},
            {"name": "Edit", "arguments": {"old_text": "100k", "new_text": "120k"}},
        ],
        "tool_results": [
            "[memory_search] Alice | salary: 100k",
            "[Edit] Edited. 4 writes left.",
        ],
    }]
    assert _check_correction_tracking(turns, "120k") is True


def test_correction_tracker_edit_budget_exhausted():
    """Correction tracker reports failure when Edit fails due to budget."""
    turns = [{
        "tool_calls": [
            {"name": "memory_search", "arguments": {"query": "Alice"}},
            {"name": "Edit", "arguments": {"old_text": "100k", "new_text": "120k"}},
        ],
        "tool_results": [
            "[memory_search] Alice | salary: 100k",
            "[Edit] Budget exhausted (30/30).",
        ],
    }]
    assert _check_correction_tracking(turns, "120k") is False


def test_correction_tracker_edit_text_not_found():
    """Correction tracker reports failure when Edit can't find old text."""
    turns = [{
        "tool_calls": [
            {"name": "memory_search", "arguments": {"query": "Alice"}},
            {"name": "Edit", "arguments": {"old_text": "100k", "new_text": "120k"}},
        ],
        "tool_results": [
            "[memory_search] Alice | salary: 100k",
            "[Edit] Text not found in memory.",
        ],
    }]
    assert _check_correction_tracking(turns, "120k") is False


def test_correction_tracker_write_budget_exhausted():
    """Correction tracker reports failure when Write fails due to budget."""
    turns = [{
        "tool_calls": [
            {"name": "Write", "arguments": {"content": "Alice | salary: 120k"}},
        ],
        "tool_results": [
            "[Write] Budget exhausted (30/30).",
        ],
    }]
    assert _check_correction_tracking(turns, "120k") is False


def test_free_edit_skips_budget():
    """Edit with free_edit=True does not consume budget."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    _execute_tool("Write", {"content": "Alice | salary: 100k"}, backend, budget)
    assert budget.writes_used == 1
    result, _ = _execute_tool(
        "Edit",
        {"old_text": "salary: 100k", "new_text": "salary: 120k"},
        backend, budget,
        free_edit=True,
    )
    assert "Edited" in result
    assert budget.writes_used == 1  # Budget unchanged


def test_free_edit_works_when_budget_exhausted():
    """Edit with free_edit=True succeeds even when budget is exhausted."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=1)
    _execute_tool("Write", {"content": "Alice | salary: 100k"}, backend, budget)
    assert budget.writes_used == 1
    assert not budget.can_write()
    result, _ = _execute_tool(
        "Edit",
        {"old_text": "salary: 100k", "new_text": "salary: 120k"},
        backend, budget,
        free_edit=True,
    )
    assert "Edited" in result
    assert budget.writes_used == 1  # Still exhausted, but Edit worked


def test_normal_edit_still_consumes_budget():
    """Edit without free_edit still consumes budget (regression check)."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    _execute_tool("Write", {"content": "Alice | salary: 100k"}, backend, budget)
    assert budget.writes_used == 1
    result, _ = _execute_tool(
        "Edit",
        {"old_text": "salary: 100k", "new_text": "salary: 120k"},
        backend, budget,
    )
    assert "Edited" in result
    assert budget.writes_used == 2  # Budget consumed


def test_free_edit_miss_no_refund_needed():
    """Edit miss with free_edit=True doesn't touch budget at all."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    _execute_tool("Write", {"content": "Alice | salary: 100k"}, backend, budget)
    result, _ = _execute_tool(
        "Edit",
        {"old_text": "nonexistent text", "new_text": "new text"},
        backend, budget,
        free_edit=True,
    )
    assert "not found" in result.lower()
    assert budget.writes_used == 1  # Only the initial Write


def test_budget_death_loop_breaks_early():
    """When budget is exhausted, _run_tool_loop must break after at most
    2 consecutive turns of all-rejected Write/Edit, not run to max_turns.

    Score-invariance: writes_used, stored_count, backend.list() must be
    identical to running the full max_turns; only api_calls/elapsed differ.
    """
    from memorygym.agents.stream_agent import _run_tool_loop

    class _ChatCompletionsStub:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kwargs):
            self.outer.calls += 1
            # Always emit a Write attempt — simulates budget death loop
            text = ('<tool_call>{"name": "Write", "arguments": '
                    '{"content": "irrelevant"}}</tool_call>')

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _MockClient:
        def __init__(self):
            self.calls = 0
            self.chat = type("C", (), {})()
            self.chat.completions = _ChatCompletionsStub(self)

    client = _MockClient()
    backend = _fresh_backend()
    # Budget pre-exhausted to force "Budget exhausted" on every Write
    budget = MemoryBudget(total_writes=5, writes_used=5)
    initial_writes_used = budget.writes_used
    initial_entries = len(backend.list())

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "ingest event"},
    ]
    stats = _run_tool_loop(
        client, "test-model", messages, backend, budget,
        max_turns=10,
    )

    # Must break after detecting 2 consecutive all-rejected turns,
    # not continue to max_turns=10
    assert stats.api_calls <= 3, (
        f"budget death loop not capped: ran {stats.api_calls} turns "
        f"(expected <=3, max_turns=10)")
    # Score-invariance: budget and backend untouched
    assert budget.writes_used == initial_writes_used
    assert len(backend.list()) == initial_entries
    # Every turn's results must be Budget exhausted
    for turn in stats.turns:
        for r in turn["tool_results"]:
            assert "Budget exhausted" in r


def test_budget_death_loop_does_not_break_when_writes_succeed():
    """When Writes succeed (budget available), loop must continue normally —
    the death-loop detector must NOT fire on healthy ingest."""
    from memorygym.agents.stream_agent import _run_tool_loop

    class _ChatCompletionsStub:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kwargs):
            self.outer.calls += 1
            if self.outer.calls < 3:
                text = ('<tool_call>{"name": "Write", "arguments": '
                        f'{{"content": "entry-{self.outer.calls}"}}}}'
                        '</tool_call>')
            else:
                # Exit gracefully on turn 3 by submitting an answer
                text = ('<tool_call>{"name": "submit_answer", '
                        '"arguments": {"answer": "done"}}</tool_call>')

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _MockClient:
        def __init__(self):
            self.calls = 0
            self.chat = type("C", (), {})()
            self.chat.completions = _ChatCompletionsStub(self)

    client = _MockClient()
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=10, writes_used=0)

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "ingest event"},
    ]
    stats = _run_tool_loop(
        client, "test-model", messages, backend, budget,
        max_turns=10,
    )

    # Both Writes should have succeeded, then submit_answer
    assert budget.writes_used == 2
    assert stats.answer == "done"
    assert stats.budget_dead_turns == 0


def test_budget_death_loop_recovers_with_search():
    """If model recovers from budget exhaustion by issuing memory_search,
    the death-loop counter must reset (model is using a non-Write tool)."""
    from memorygym.agents.stream_agent import _run_tool_loop

    class _ChatCompletionsStub:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kwargs):
            self.outer.calls += 1
            if self.outer.calls == 1:
                # rejected Write
                text = ('<tool_call>{"name": "Write", "arguments": '
                        '{"content": "x"}}</tool_call>')
            elif self.outer.calls == 2:
                # model pivots to search — counter resets
                text = ('<tool_call>{"name": "memory_search", '
                        '"arguments": {"query": "x"}}</tool_call>')
            else:
                text = ('<tool_call>{"name": "submit_answer", '
                        '"arguments": {"answer": "ok"}}</tool_call>')

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _MockClient:
        def __init__(self):
            self.calls = 0
            self.chat = type("C", (), {})()
            self.chat.completions = _ChatCompletionsStub(self)

    client = _MockClient()
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=1, writes_used=1)  # exhausted

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "event"},
    ]
    stats = _run_tool_loop(
        client, "test-model", messages, backend, budget,
        max_turns=10,
    )

    # Loop should reach submit_answer, NOT break early
    assert stats.answer == "ok"
    assert stats.api_calls == 3
    # Counter reset by the search turn
    assert stats.budget_dead_turns == 0


def _make_failing_client(exc_factory, *, fail_until_call: int = 10**9):
    """Build a mock OpenAI client that raises on every call up to limit."""

    class _ChatCompletionsStub:
        def __init__(self, outer):
            self.outer = outer

        def create(self, **kwargs):
            self.outer.calls += 1
            if self.outer.calls <= fail_until_call:
                raise exc_factory(self.outer.calls)
            text = (
                '<tool_call>{"name": "submit_answer", '
                '"arguments": {"answer": "ok"}}</tool_call>'
            )

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _MockClient:
        def __init__(self):
            self.calls = 0
            self.chat = type("C", (), {})()
            self.chat.completions = _ChatCompletionsStub(self)

        def close(self):  # parity with real OpenAI client
            pass

    return _MockClient()


def test_run_stream_agent_continues_past_infra_failures(monkeypatch):
    """A single LLM call exhausting retries must NOT abort the whole eval.

    Failed events become abstain/no-op; the agent's prior storage and any
    earlier correct answers are preserved. This is the dominant failure
    mode in production (see executor logs: 'Eval model unreachable after
    10 retries' caused 100% loss of partial work).
    """
    from memorygym.agents import stream_agent as sa
    from memorygym.worlds import ALL_TEMPLATES

    # Mock OpenAI to always raise 429 -> single LLM call exhausts retries
    # quickly. We patch the client constructor to return our mock and we
    # patch time.sleep to skip the exp-backoff waits.
    fake_client = _make_failing_client(
        lambda i: Exception("Error code: 429 - Infrastructure at maximum capacity")
    )
    monkeypatch.setattr(sa, "OpenAI", lambda **kw: fake_client)
    monkeypatch.setattr(sa.time, "sleep", lambda *a, **kw: None)

    tmpl = ALL_TEMPLATES["company"]()
    world = tmpl.generate_world(seed=1, n_entities=8, eval_salt=1)
    rng = __import__("random").Random(1)
    stream = tmpl.generate_stream(
        world, rng, corrections=[], stored_names=set(),
        n_questions=4, entities_per_batch=4, contradictions=[],
    )

    backend = _fresh_backend()
    results, writes_used, stored, eval_error, traj = sa.run_stream_agent(
        model="mock-model",
        stream=stream,
        write_budget=10,
        api_base="http://mock",
        api_key="mock",
        backend=backend,
        world=world,
        template=tmpl,
        seed=1,
        quiet=True,
    )

    # Eval error must be set (provider down or majority-failed), but the
    # function must NOT have raised. Trajectory and result list must be
    # populated rather than empty/half-built.
    assert eval_error is not None, "expected eval_error to be set"
    assert (
        "provider_unreachable" in eval_error
        or "too_many_infra_failures" in eval_error
    ), f"unexpected eval_error: {eval_error}"
    # Trajectory entries record the infra error rather than crashing.
    assert any(
        "infra_error" in t and t.get("infra_error")
        for t in traj
    ), "trajectory must record infra_error markers"


def test_run_stream_agent_partial_completion_under_threshold(monkeypatch):
    """When fewer than half of questions hit infra-fail, eval should
    return without setting eval_error so the partially-completed
    sample is still scored (efficiency: don't throw away good data)."""
    from memorygym.agents import stream_agent as sa
    from memorygym.worlds import ALL_TEMPLATES

    state = {"calls": 0}

    class _Stub:
        def create(self, **kwargs):
            state["calls"] += 1
            # Fail every 5th call only — sparse 429 pattern
            if state["calls"] % 5 == 0:
                raise Exception("Error code: 429 - capacity")
            text = (
                '<tool_call>{"name": "submit_answer", '
                '"arguments": {"answer": "I don\'t have enough information"}}'
                "</tool_call>"
            )

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    monkeypatch.setattr(sa, "OpenAI", lambda **kw: _Client())
    monkeypatch.setattr(sa.time, "sleep", lambda *a, **kw: None)
    # Judge runs at end of eval; with abstain answers we'd otherwise
    # spin in JUDGE_TIMEOUT_S retrying on the same failing mock client.
    monkeypatch.setattr(
        sa, "llm_judge_validate_sync",
        lambda *a, **kw: (False, "abstain"),
    )

    tmpl = ALL_TEMPLATES["company"]()
    world = tmpl.generate_world(seed=2, n_entities=10, eval_salt=1)
    rng = __import__("random").Random(2)
    stream = tmpl.generate_stream(
        world, rng, corrections=[], stored_names=set(),
        n_questions=20, entities_per_batch=5, contradictions=[],
    )

    backend = _fresh_backend()
    results, _, _, eval_error, _ = sa.run_stream_agent(
        model="mock-model",
        stream=stream,
        write_budget=20,
        api_base="http://mock",
        api_key="mock",
        backend=backend,
        world=world,
        template=tmpl,
        seed=2,
        quiet=True,
    )

    # Most questions should have been answered (model abstained, but no
    # infra error). eval_error must remain None so the sample is scored.
    assert eval_error is None, (
        f"expected no eval_error for sparse failures, got: {eval_error}")
    infra_q = sum(1 for r in results if r.error)
    assert infra_q < len(results) / 2, (
        f"too many infra-failed questions: {infra_q}/{len(results)}")


def test_run_stream_agent_wallclock_budget_finalizes_early(monkeypatch):
    """Soft wallclock budget must stop the event loop before the validator
    kills the process at proxy_timeout. Partial results survive."""
    from memorygym.agents import stream_agent as sa
    from memorygym.worlds import ALL_TEMPLATES

    class _Stub:
        def create(self, **kwargs):
            text = (
                '<tool_call>{"name": "submit_answer", '
                '"arguments": {"answer": "fast"}}</tool_call>'
            )

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    monkeypatch.setattr(sa, "OpenAI", lambda **kw: _Client())

    tmpl = ALL_TEMPLATES["company"]()
    world = tmpl.generate_world(seed=3, n_entities=10, eval_salt=1)
    rng = __import__("random").Random(3)
    stream = tmpl.generate_stream(
        world, rng, corrections=[], stored_names=set(),
        n_questions=20, entities_per_batch=5, contradictions=[],
    )

    backend = _fresh_backend()
    results, _, _, eval_error, traj = sa.run_stream_agent(
        model="mock-model",
        stream=stream,
        write_budget=20,
        api_base="http://mock",
        api_key="mock",
        backend=backend,
        world=world,
        template=tmpl,
        seed=3,
        quiet=True,
        wallclock_budget=0.001,  # immediately breached on second event
    )

    # Hit the wallclock budget on the very first iteration — only one
    # event (the first ingest) should have been processed. Since no
    # question was answered, the eval should be marked
    # wallclock_before_questions so the validator excludes it instead of
    # recording a misleading score=0 RESULT.
    expected_markers = (
        "wallclock_before_questions", "too_many", "wallclock_no_judge_time",
        "judge_incomplete",
    )
    assert eval_error is None or any(m in (eval_error or "")
                                      for m in expected_markers), (
        f"unexpected eval_error: {eval_error}")
    assert len(traj) <= 3, (
        f"wallclock budget should have stopped processing early; "
        f"got {len(traj)} trajectory entries")


def test_run_tool_loop_treats_request_timed_out_as_transient(monkeypatch):
    """OpenAI APITimeoutError uses message 'Request timed out.' (two
    words). A previous bug checked only for 'timeout' substring, missed
    'timed out', and propagated the exception out of the tool loop —
    bypassing every graceful-continuation guard. Live observation
    2026-05-02: 4/4 memory samples in 1h died with this error before
    the fix.
    """
    from memorygym.agents.stream_agent import _run_tool_loop
    import memorygym.agents.stream_agent as sa

    state = {"calls": 0}

    class _Stub:
        def create(self, **kwargs):
            state["calls"] += 1
            # OpenAI APITimeoutError-style message — exactly what the SDK
            # emits when a request exceeds its read timeout. No 'timeout'
            # substring (one word), only 'timed out' (two words).
            raise Exception("Request timed out.")

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    monkeypatch.setattr(sa.time, "sleep", lambda *a, **kw: None)

    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)

    stats = _run_tool_loop(
        _Client(), "test-model",
        [{"role": "system", "content": "x"},
         {"role": "user", "content": "y"}],
        backend, budget,
        max_turns=1, max_retries=3,
    )

    # Must be treated as transient → retried 3 times → exhausted with
    # stats.error set. NOT raised out of the tool loop (which would
    # bypass graceful continuation in the outer event loop).
    assert stats.error is not None, (
        "expected 'Request timed out.' to be caught and converted to "
        "stats.error, but it was raised out of the tool loop")
    assert "Request timed out" in stats.error or "unreachable" in stats.error
    assert state["calls"] == 4, (
        f"expected initial + 3 retries = 4 calls; got {state['calls']}")


def test_run_tool_loop_honors_wallclock_deadline_during_retries(monkeypatch):
    """A retry storm must not cross the wallclock deadline. The retry
    chain has a max idle of 10×60s=600s; without this guard, the eval
    can overshoot the validator's hard kill (7210s) on a single LLM
    call and lose all partial work. The fix surfaces a wallclock
    error so the outer loop finalizes immediately."""
    from memorygym.agents.stream_agent import _run_tool_loop

    state = {"calls": 0}

    class _FailingStub:
        def create(self, **kwargs):
            state["calls"] += 1
            raise Exception("Error code: 429 - capacity")

    class _Client:
        chat = type("C", (), {"completions": _FailingStub()})()

        def close(self):
            pass

    # Patch sleep so the deadline check is the only thing that can
    # break the retry loop — otherwise the test would itself wait.
    import memorygym.agents.stream_agent as sa
    monkeypatch.setattr(sa.time, "sleep", lambda *a, **kw: None)

    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)

    import time as _t
    deadline = _t.time() - 1  # already passed
    stats = _run_tool_loop(
        _Client(), "test-model",
        [{"role": "system", "content": "x"},
         {"role": "user", "content": "y"}],
        backend, budget,
        max_turns=10, max_retries=10,
        wallclock_deadline=deadline,
    )

    # Should bail immediately, not run the full 10 retries
    assert stats.error is not None, "expected stats.error to be set"
    assert "wallclock" in stats.error.lower(), (
        f"expected wallclock_exhausted error, got: {stats.error}")
    # Calls should be at most a handful (one initial + a couple retries
    # before deadline check fires) — definitely far under 10.
    assert state["calls"] <= 3, (
        f"deadline guard didn't trip fast enough: {state['calls']} calls")


def test_parse_retry_after_extracts_seconds():
    """Provider's Retry-After header (seconds) should override exp-backoff."""
    from memorygym.agents.stream_agent import _parse_retry_after

    class _FakeHeaders(dict):
        pass

    class _FakeResponse:
        def __init__(self, headers):
            self.headers = _FakeHeaders(headers)

    class _FakeExc(Exception):
        def __init__(self, headers):
            super().__init__("rate limited")
            self.response = _FakeResponse(headers)

    # Standard Retry-After
    assert _parse_retry_after(_FakeExc({"Retry-After": "30"})) == 30.0
    # Lowercase
    assert _parse_retry_after(_FakeExc({"retry-after": "5"})) == 5.0
    # Cap at 120
    assert _parse_retry_after(_FakeExc({"Retry-After": "9999"})) == 120.0
    # Floor at 1
    assert _parse_retry_after(_FakeExc({"Retry-After": "0.1"})) == 1.0
    # Float input
    assert _parse_retry_after(_FakeExc({"Retry-After": "12.5"})) == 12.5
    # Missing header -> None
    assert _parse_retry_after(_FakeExc({})) is None
    # No response attribute -> None
    assert _parse_retry_after(Exception("plain")) is None
    # Bad value (HTTP-date) -> None (skipped)
    assert _parse_retry_after(
        _FakeExc({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
    ) is None


def test_run_tool_loop_uses_retry_after_hint(monkeypatch):
    """When the 429 carries a Retry-After header, the wait time should
    match the hint instead of the exp-backoff value."""
    from memorygym.agents.stream_agent import _run_tool_loop
    import memorygym.agents.stream_agent as sa

    class _Hdrs(dict):
        pass

    class _Resp:
        def __init__(self, hdrs):
            self.headers = _Hdrs(hdrs)

    class _Exc(Exception):
        def __init__(self, msg, hdrs):
            super().__init__(msg)
            self.response = _Resp(hdrs)

    # Always raise 429 with Retry-After=7s
    state = {"calls": 0, "sleeps": []}

    class _Stub:
        def create(self, **kwargs):
            state["calls"] += 1
            raise _Exc("Error code: 429 - capacity",
                       {"Retry-After": "7"})

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    monkeypatch.setattr(sa.time, "sleep",
                        lambda s: state["sleeps"].append(s))

    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)

    stats = _run_tool_loop(
        _Client(), "test", [
            {"role": "system", "content": "x"},
            {"role": "user", "content": "y"},
        ],
        backend, budget,
        max_turns=1, max_retries=3,
    )

    # All sleep durations should equal the hint (7.0), not exp backoff (5,10,20)
    assert stats.error is not None, "expected stats.error"
    assert all(s == 7.0 for s in state["sleeps"]), (
        f"expected all sleeps to equal Retry-After hint of 7s; got {state['sleeps']}")
    assert len(state["sleeps"]) == 3, (
        f"expected exactly 3 retries before exhausting max_retries=3; "
        f"got {len(state['sleeps'])}")


def test_run_tool_loop_passes_dynamic_timeout_to_llm_client(monkeypatch):
    """Fix A: each LLM call must receive a `timeout=` kwarg derived from
    the remaining wallclock. Without this, the SDK default 600s timeout
    can let a slow call overshoot the eval's wallclock_deadline and
    trigger the affinetes 7210s server-side kill."""
    from memorygym.agents.stream_agent import _run_tool_loop
    import memorygym.agents.stream_agent as sa
    import time as _t

    captured_timeouts: list = []

    class _Stub:
        def create(self, **kwargs):
            captured_timeouts.append(kwargs.get("timeout"))
            text = (
                '<tool_call>{"name": "submit_answer", '
                '"arguments": {"answer": "ok"}}</tool_call>'
            )

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    deadline = _t.time() + 100  # 100s remaining

    stats = _run_tool_loop(
        _Client(), "test", [
            {"role": "system", "content": "x"},
            {"role": "user", "content": "y"},
        ],
        backend, budget,
        max_turns=1, max_retries=3,
        wallclock_deadline=deadline,
    )

    assert stats.error is None, f"unexpected error: {stats.error}"
    assert len(captured_timeouts) >= 1, (
        f"expected at least one LLM call; got {len(captured_timeouts)}")
    # Timeout must be a finite number derived from remaining wallclock
    for t in captured_timeouts:
        assert t is not None, "timeout was not passed to LLM client"
        assert 30.0 <= t <= 300.0, (
            f"timeout out of expected bounds [30, 300]: {t}")


def test_run_tool_loop_no_timeout_when_wallclock_deadline_absent(monkeypatch):
    """Fix A negative case: when no wallclock_deadline is configured
    (e.g. local testing), no timeout should be passed — preserve current
    SDK default behavior. Avoids accidentally regressing offline use."""
    from memorygym.agents.stream_agent import _run_tool_loop

    captured_kwargs: list = []

    class _Stub:
        def create(self, **kwargs):
            captured_kwargs.append(kwargs)
            text = (
                '<tool_call>{"name": "submit_answer", '
                '"arguments": {"answer": "ok"}}</tool_call>'
            )

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)

    _run_tool_loop(
        _Client(), "test", [
            {"role": "system", "content": "x"},
            {"role": "user", "content": "y"},
        ],
        backend, budget,
        max_turns=1, max_retries=3,
        wallclock_deadline=None,
    )

    assert "timeout" not in captured_kwargs[0], (
        f"timeout should NOT be set when no wallclock_deadline; "
        f"got kwargs={list(captured_kwargs[0].keys())}")


def test_judge_phase_skipped_when_past_wallclock(monkeypatch):
    """Fix B: when the agent loop exits past the wallclock_deadline,
    the judge phase must skip rather than blocking for ~600s per pending
    answer. Otherwise judge can push runtime past the 7210s server kill."""
    from memorygym.agents import stream_agent as sa
    from memorygym.worlds import ALL_TEMPLATES

    judge_call_count = {"n": 0}

    def _slow_judge(*args, **kwargs):
        judge_call_count["n"] += 1
        # Simulate a slow judge — should NEVER be called when past wallclock
        import time as _t
        _t.sleep(60)
        return False, "should not be called"

    monkeypatch.setattr(sa, "llm_judge_validate_sync", _slow_judge)

    # Mock OpenAI to return abstain answers (which fail rule and would
    # normally go to judge)
    class _Stub:
        def create(self, **kwargs):
            text = (
                '<tool_call>{"name": "submit_answer", '
                '"arguments": {"answer": "wrong-answer-needs-judge"}}'
                "</tool_call>"
            )

            class _Msg:
                content = text

            class _Choice:
                message = _Msg()

            class _Resp:
                choices = [_Choice()]

            return _Resp()

    class _Client:
        chat = type("C", (), {"completions": _Stub()})()

        def close(self):
            pass

    monkeypatch.setattr(sa, "OpenAI", lambda **kw: _Client())

    tmpl = ALL_TEMPLATES["company"]()
    world = tmpl.generate_world(seed=11, n_entities=8, eval_salt=1)
    rng = __import__("random").Random(11)
    stream = tmpl.generate_stream(
        world, rng, corrections=[], stored_names=set(),
        n_questions=4, entities_per_batch=4, contradictions=[],
    )

    # Tiny wallclock budget to force agent to exit immediately, putting
    # us past the deadline before the judge phase begins.
    backend = _fresh_backend()
    results, _, _, eval_error, _ = sa.run_stream_agent(
        model="mock", stream=stream, write_budget=10,
        api_base="http://mock", api_key="mock",
        backend=backend, world=world, template=tmpl, seed=11,
        quiet=True,
        wallclock_budget=0.001,  # immediately past deadline
    )

    # If the wallclock guard is missing, _slow_judge would block 60s+
    # per pending answer. With the guard, judge is skipped entirely.
    assert judge_call_count["n"] == 0, (
        f"judge should be skipped when past wallclock; got "
        f"{judge_call_count['n']} judge calls")
    # And the eval should mark itself as no-judge-time
    assert eval_error and ("wallclock" in eval_error
                           or "judge" in eval_error.lower()), (
        f"expected wallclock/judge marker in eval_error; got: {eval_error}")


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            sys.exit(1)
    print("ALL TESTS PASSED")
