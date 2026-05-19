import json

from memorygym.agents.affent_agent import (
    _apply_memory_budget,
    _load_memory_state,
    _parse_trace,
    _resolve_affentctl,
    _write_affent_memory_entries,
)
from memorygym.memory.budget import MemoryBudget


def _event(event_type, data):
    return {"id": 1, "type": event_type, "data": data}


def test_resolve_affentctl_from_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    affentctl = bin_dir / "affentctl"
    affentctl.write_text("#!/bin/sh\n")
    affentctl.chmod(0o755)
    monkeypatch.delenv("AFFENTCTL_BIN", raising=False)
    monkeypatch.setenv("PATH", str(bin_dir))

    assert _resolve_affentctl() == str(affentctl)


def test_parse_affent_trace_memory_tool(tmp_path):
    trace = tmp_path / "trace.jsonl"
    events = [
        _event("tool.request", {
            "tool": "memory",
            "args": {
                "action": "add",
                "target": "memory",
                "content": "Alice | salary: 100k",
            },
        }),
        _event("tool.result", {
            "result_summary": '{"ok":true,"target":"memory","entries":["Alice | salary: 100k"]}',
        }),
        _event("usage", {"input_tokens": 10, "output_tokens": 5}),
        _event("message.done", {"text": "Stored."}),
        _event("turn.end", {"reason": "completed"}),
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events))

    turn = _parse_trace(trace)

    assert turn.answer == "Stored."
    assert turn.searches == 0
    assert turn.writes == 1
    assert turn.api_calls == 1
    assert turn.error is None
    assert turn.turns[0]["tool_calls"][0]["name"] == "memory"


def test_parse_affent_trace_final_text_fallback(tmp_path):
    trace = tmp_path / "trace.jsonl"
    trace.write_text(json.dumps(_event(
        "message.done",
        {"text": "<think>private reasoning</think>I don't know"},
    )))

    turn = _parse_trace(trace)

    assert turn.answer == "I don't know"
    assert turn.api_calls == 1


def test_load_affent_markdown_memory(tmp_path):
    _write_affent_memory_entries(tmp_path, [
        "Alice | salary: 100k",
        "Bob | salary: 200k",
    ])

    state = _load_memory_state(tmp_path)

    assert state["writes_used"] == 0
    assert state["entries"][0]["content"] == "Alice | salary: 100k"
    assert state["entries"][1]["content"] == "Bob | salary: 200k"


def test_apply_memory_budget_replays_successful_memory_calls(tmp_path):
    budget = MemoryBudget(total_writes=1)
    turns = [{
        "tool_calls": [
            {
                "name": "memory",
                "arguments": {
                    "action": "add",
                    "target": "memory",
                    "content": "Alice | salary: 100k",
                },
            },
            {
                "name": "memory",
                "arguments": {
                    "action": "add",
                    "target": "memory",
                    "content": "Bob | salary: 200k",
                },
            },
        ],
        "tool_results": [
            '[tool] {"ok":true,"target":"memory","entries":["Alice | salary: 100k"]}',
            '[tool] {"ok":true,"target":"memory","entries":["Alice | salary: 100k","Bob | salary: 200k"]}',
        ],
    }]

    writes = _apply_memory_budget(tmp_path, [], turns, budget)
    state = _load_memory_state(tmp_path)

    assert writes == 1
    assert budget.writes_used == 1
    assert [e["content"] for e in state["entries"]] == ["Alice | salary: 100k"]
