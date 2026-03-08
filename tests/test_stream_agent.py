"""Tests for stream_agent tool parsing and execution (no API calls)."""

from memorygym.agents.stream_agent import (
    _execute_tool,
    _extract_tool_calls,
    _parse_and_execute,
    _format_documents,
    SYSTEM_PROMPT,
    _TOOL_CALL_RE,
)
from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.memory.budget import MemoryBudget


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
    assert "memory_store" in prompt
    assert "submit_answer" in prompt


def test_store_with_memory_id_update():
    """memory_store with memory_id updates existing entry."""
    backend = _fresh_backend()
    budget = MemoryBudget(total_writes=5)
    entry_id = backend.store("Alice | salary: 100k")
    result, answer = _execute_tool(
        "memory_store",
        {"content": "Alice | salary: 120k", "memory_id": entry_id},
        backend, budget,
    )
    assert "Stored" in result
    entries = backend.list()
    assert len(entries) == 1
    assert "120k" in entries[0]["content"]


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
