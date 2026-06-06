import json
import time
from types import SimpleNamespace

from memorygym.agents.affent_agent import (
    _apply_memory_budget,
    _correction_applied,
    _load_memory_state,
    _new_judge_client,
    _parse_trace,
    _read_affent_memory_entries,
    _resolve_affentctl,
    _run_affent_turn,
    _run_affent_turn_with_retries,
    _write_eval_config,
    _write_affent_memory_entries,
    run_affent_agent,
)
from memorygym.memory.budget import MemoryBudget


def _event(event_type, data):
    return {"id": 1, "type": event_type, "data": data}


def _affent_turn(
    answer=None,
    final_text="",
    writes=0,
    searches=0,
    api_calls=0,
    elapsed=0.0,
    error=None,
    stop_reason=None,
    turns=None,
):
    return SimpleNamespace(
        answer=answer,
        final_text=final_text,
        writes=writes,
        searches=searches,
        api_calls=api_calls,
        elapsed=elapsed,
        error=error,
        stop_reason=stop_reason,
        turns=turns or [],
    )


def _patch_affent_runner(monkeypatch, fake_turn):
    monkeypatch.setattr(
        "memorygym.agents.affent_agent._resolve_affentctl",
        lambda explicit=None: "/bin/true",
    )
    monkeypatch.setattr(
        "memorygym.agents.affent_agent._new_judge_client",
        lambda: None,
    )
    monkeypatch.setattr(
        "memorygym.agents.affent_agent._run_affent_turn_with_retries",
        fake_turn,
    )


def _ingest_event(name, role):
    return {
        "type": "ingest",
        "entity_names": [name],
        "documents": [f"{name} | role: {role}"],
    }


def _question_event(question, answer, entity):
    return {
        "type": "question",
        "question": question,
        "answer": answer,
        "competency": "retrieval",
        "purpose": "recall",
        "required_entities": [entity],
        "source_attr": "role",
    }


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


def test_parse_affent_trace_prefers_full_result_over_summary(tmp_path):
    """When affent emits both `result` (full) and `result_summary`
    (truncated UI preview), the parser must record the full one so
    downstream JSON parsing succeeds for large memory responses.
    """
    # 5 KB payload exceeds affent's 4 KB result_summary cap; only the
    # `result` field still carries valid JSON.
    big_entries = [f"entry-{i:03d}" for i in range(250)]
    full_json = json.dumps({"ok": True, "target": "memory", "entries": big_entries})
    truncated = full_json[:4096] + "..."  # mimics affent previewN()

    trace = tmp_path / "trace.jsonl"
    events = [
        _event("tool.request", {
            "tool": "memory",
            "args": {"action": "add", "target": "memory", "content": "x"},
        }),
        _event("tool.result", {
            "result_summary": truncated,
            "result": full_json,
        }),
        _event("turn.end", {"reason": "completed"}),
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events))

    turn = _parse_trace(trace)
    assert len(turn.turns) == 1
    captured = turn.turns[0]["tool_results"][0]
    assert captured.startswith("[tool] ")
    body = captured[len("[tool] "):]
    parsed = json.loads(body)  # MUST parse — would fail without the fix
    assert parsed["ok"] is True
    assert len(parsed["entries"]) == 250


def test_parse_affent_trace_falls_back_to_summary_when_no_result(tmp_path):
    """Old affent binaries do not emit the `result` field. The parser
    must fall back to `result_summary` so legacy traces still work.
    """
    trace = tmp_path / "trace.jsonl"
    events = [
        _event("tool.request", {
            "tool": "memory",
            "args": {"action": "add", "target": "memory", "content": "y"},
        }),
        _event("tool.result", {
            "result_summary": '{"ok":true,"target":"memory"}',
        }),
        _event("turn.end", {"reason": "completed"}),
    ]
    trace.write_text("\n".join(json.dumps(e) for e in events))

    turn = _parse_trace(trace)
    captured = turn.turns[0]["tool_results"][0]
    assert "ok" in captured


def test_write_eval_config_sets_balanced_topic_limit(tmp_path):
    path = _write_eval_config(tmp_path, "sys")
    cfg = json.loads(path.read_text())

    # Topic count must permit real organization while preserving summarization
    # pressure through affent's per-topic char limit.
    assert cfg["memory"]["max_topics"] == 8
    assert "topic_max_chars" not in cfg["memory"]
    assert cfg["memory"]["user_store"] == str(tmp_path / ".affent" / "USER.md")
    assert cfg["max_call_timeout"] == "10m"
    assert cfg["retry_transient"] == 10


def test_run_affent_turn_passes_config_and_timeout(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        trace_path = cmd[cmd.index("--trace") + 1]
        with open(trace_path, "w") as f:
            f.write(json.dumps(_event("message.done", {"text": "ok"})))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("memorygym.agents.affent_agent.subprocess.run", fake_run)
    config = _write_eval_config(tmp_path, "sys")

    turn = _run_affent_turn(
        affent_bin="/bin/affentctl",
        workspace=tmp_path,
        model="model",
        base_url="http://example/v1",
        api_key="key",
        config_path=config,
        session_id="s",
        prompt="hi",
    )

    assert turn.answer == "ok"
    assert captured["cmd"][captured["cmd"].index("--config") + 1] == str(config)
    assert captured["cmd"][captured["cmd"].index("--memory-max-topics") + 1] == "8"


def test_run_affent_turn_retries_transient_failure(tmp_path, monkeypatch):
    calls = []
    restores = []

    def fake_restore(workspace, before_state):
        restores.append([dict(x) for x in before_state])

    def fake_turn(**kwargs):
        calls.append(kwargs["session_id"])
        if len(calls) == 1:
            return SimpleNamespace(
                answer=None,
                final_text="",
                writes=0,
                searches=0,
                api_calls=0,
                elapsed=0.0,
                error="affentctl exited 3: [llm_stream] stream read: unexpected EOF",
                stop_reason=None,
                turns=[],
            )
        return SimpleNamespace(
            answer="ok",
            final_text="ok",
            writes=0,
            searches=0,
            api_calls=1,
            elapsed=0.0,
            error=None,
            stop_reason="completed",
            turns=[{"content": "ok"}],
        )

    monkeypatch.setattr(
        "memorygym.agents.affent_agent._write_affent_memory_state",
        fake_restore,
    )
    monkeypatch.setattr("memorygym.agents.affent_agent._run_affent_turn", fake_turn)

    turn = _run_affent_turn_with_retries(
        affent_bin="/bin/affentctl",
        workspace=tmp_path,
        model="model",
        base_url="http://example/v1",
        api_key="key",
        config_path=_write_eval_config(tmp_path, "sys"),
        session_id="s",
        prompt="hi",
        before_state=[{"topic": "general", "content": "alpha"}],
        quiet=True,
    )

    assert calls == ["s", "s_retry1"]
    assert len(restores) == 1
    assert turn.answer == "ok"
    assert turn.error is None


def test_new_judge_client_requires_explicit_judge_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("CHUTES_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "dummy-target-model-key")

    assert _new_judge_client() is None


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


def _ok(entries):
    return '[tool] ' + json.dumps({"ok": True, "target": "memory", "entries": entries})


def test_correction_applied_true_on_anchored_replace():
    turns = [{
        "tool_calls": [{
            "name": "memory",
            "arguments": {
                "action": "replace",
                "target": "memory",
                "old_text": "Alice | salary",
                "content": "Alice | salary: 250k",
            },
        }],
        "tool_results": [_ok(["Alice | salary: 250k"])],
    }]
    assert _correction_applied(turns, entity_name="Alice", new_val="250k") is True


def test_correction_applied_false_when_old_text_not_anchored_on_entity():
    """The regression: agent replaces an unrelated entry whose new
    content happens to mention new_val. Must NOT count as a correct
    correction — the targeted entity was never touched."""
    turns = [{
        "tool_calls": [{
            "name": "memory",
            "arguments": {
                "action": "replace",
                # Replacing Bob's entry, but the correction event is for Alice.
                "old_text": "Bob | salary",
                "content": "Bob now mentions 250k somewhere",
            },
        }],
        "tool_results": [_ok(["Bob now mentions 250k somewhere"])],
    }]
    assert _correction_applied(turns, entity_name="Alice", new_val="250k") is False


def test_correction_applied_false_when_replace_call_failed():
    turns = [{
        "tool_calls": [{
            "name": "memory",
            "arguments": {
                "action": "replace",
                "old_text": "Alice | salary",
                "content": "Alice | salary: 250k",
            },
        }],
        "tool_results": [
            '[tool] {"ok":false,"target":"memory","message":"no entry matched"}'
        ],
    }]
    assert _correction_applied(turns, entity_name="Alice", new_val="250k") is False


def test_write_affent_memory_entries_atomic_no_temp_leftovers(tmp_path):
    _write_affent_memory_entries(tmp_path, ["one", "two"])
    # Atomic implementations stage via a temp file in the same dir
    # before rename; the temp file must NOT outlive the call.
    mem_dir = tmp_path / ".affent"
    leftovers = list(mem_dir.glob(".mem-*.tmp")) + list(mem_dir.glob("*.tmp"))
    assert not leftovers, f"unexpected temp files: {leftovers}"
    assert _read_affent_memory_entries(tmp_path) == ["one", "two"]


def test_apply_memory_budget_skips_write_when_no_mutations(tmp_path):
    """Question events trigger _apply_memory_budget with no memory
    tool calls. The function must not rewrite the memory file when nothing
    changed — preserves mtime and avoids needless disk churn."""
    _write_affent_memory_entries(tmp_path, ["alpha", "beta"])
    mem_file = tmp_path / ".affent" / "memory" / "topics" / "general.md"
    before_mtime = mem_file.stat().st_mtime_ns

    # A pure question turn: model just answered, no tool calls.
    turns = [{"tool_calls": [], "tool_results": []}]
    budget = MemoryBudget(total_writes=10)
    time.sleep(0.01)  # ensure mtime would change if a write happened

    before_state = [
        {"topic": "general", "content": "alpha"},
        {"topic": "general", "content": "beta"},
    ]
    writes = _apply_memory_budget(tmp_path, before_state, turns, budget)

    after_mtime = mem_file.stat().st_mtime_ns
    assert writes == 0
    assert after_mtime == before_mtime, "MEMORY.md must not be rewritten on no-op turn"
    assert _read_affent_memory_entries(tmp_path) == ["alpha", "beta"]


def test_run_affent_agent_cleans_owned_temp_workspace(tmp_path, monkeypatch):
    owned = tmp_path / "owned"

    monkeypatch.setattr(
        "memorygym.agents.affent_agent.tempfile.mkdtemp",
        lambda prefix: str(owned),
    )
    monkeypatch.setattr(
        "memorygym.agents.affent_agent._resolve_affentctl",
        lambda explicit=None: "/bin/true",
    )

    run_affent_agent(
        model="model",
        stream=[],
        api_base="http://example/v1",
        api_key="key",
    )

    assert not owned.exists()


def test_run_affent_agent_preserves_explicit_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "explicit"

    monkeypatch.setattr(
        "memorygym.agents.affent_agent._resolve_affentctl",
        lambda explicit=None: "/bin/true",
    )

    run_affent_agent(
        model="model",
        stream=[],
        api_base="http://example/v1",
        api_key="key",
        workspace=str(workspace),
    )

    assert workspace.exists()


def test_run_affent_agent_stops_sample_on_infra_error(tmp_path, monkeypatch):
    calls = []

    def fake_turn(**kwargs):
        calls.append(kwargs["prompt"])
        return _affent_turn(
            error="affentctl exited 3: stream read: unexpected EOF",
        )

    _patch_affent_runner(monkeypatch, fake_turn)
    stream = [_ingest_event("Alice", "engineer"), _ingest_event("Bob", "designer")]

    results, writes_used, stored, eval_error, trajectory = run_affent_agent(
        model="model",
        stream=stream,
        write_budget=2,
        api_base="http://example/v1",
        api_key="key",
        workspace=str(tmp_path / "workspace"),
        quiet=True,
    )

    assert results == []
    assert writes_used == 0
    assert stored == []
    assert "unexpected EOF" in eval_error
    assert len(calls) == 1
    assert [event["type"] for event in trajectory] == ["system", "ingest"]


def test_run_affent_agent_continues_on_max_turns_behavior(tmp_path, monkeypatch):
    calls = []

    def fake_turn(**kwargs):
        calls.append(kwargs["prompt"])
        return _affent_turn(
            api_calls=1,
            error="affent turn ended: max_turns",
            stop_reason="max_turns",
        )

    _patch_affent_runner(monkeypatch, fake_turn)
    stream = [_ingest_event("Alice", "engineer"), _ingest_event("Bob", "designer")]

    results, writes_used, stored, eval_error, trajectory = run_affent_agent(
        model="model",
        stream=stream,
        write_budget=2,
        api_base="http://example/v1",
        api_key="key",
        workspace=str(tmp_path / "workspace"),
        quiet=True,
    )

    assert results == []
    assert writes_used == 0
    assert stored == []
    assert eval_error is None
    assert len(calls) == 2
    assert [event["type"] for event in trajectory] == [
        "system",
        "ingest",
        "ingest",
    ]


def test_run_affent_agent_scores_remaining_questions_after_wallclock(
    tmp_path, monkeypatch,
):
    calls = []

    def fake_turn(**kwargs):
        calls.append(kwargs["prompt"])
        return _affent_turn(
            answer="one",
            final_text="one",
            api_calls=1,
            stop_reason="completed",
            turns=[{"content": "one"}],
        )

    times = iter([100.0, 100.0, 100.0, 111.0])
    monkeypatch.setattr(
        "memorygym.agents.affent_agent.time.time",
        lambda: next(times),
    )
    _patch_affent_runner(monkeypatch, fake_turn)
    stream = [
        _question_event("First?", "one", "Alice"),
        _question_event("Second?", "two", "Bob"),
    ]

    results, writes_used, stored, eval_error, trajectory = run_affent_agent(
        model="model",
        stream=stream,
        write_budget=2,
        api_base="http://example/v1",
        api_key="key",
        workspace=str(tmp_path / "workspace"),
        wallclock_budget=10.0,
        quiet=True,
    )

    assert eval_error is None
    assert writes_used == 0
    assert stored == []
    assert len(calls) == 1
    assert len(results) == 2
    assert results[0].correct is True
    assert results[1].correct is False
    assert results[1].validation_method == "wallclock"
    assert trajectory[-1]["stop_reason"] == "unanswered_after_wallclock"


def test_run_affent_agent_scores_question_timeout_after_entering_question(
    tmp_path, monkeypatch,
):
    calls = []

    def fake_turn(**kwargs):
        calls.append(kwargs["prompt"])
        return _affent_turn(
            error="affent turn timed out",
        )

    _patch_affent_runner(monkeypatch, fake_turn)
    stream = [
        _question_event("First?", "one", "Alice"),
        _question_event("Second?", "two", "Bob"),
    ]

    results, writes_used, stored, eval_error, trajectory = run_affent_agent(
        model="model",
        stream=stream,
        write_budget=2,
        api_base="http://example/v1",
        api_key="key",
        workspace=str(tmp_path / "workspace"),
        quiet=True,
    )

    assert eval_error is None
    assert writes_used == 0
    assert stored == []
    assert len(calls) == 1
    assert len(results) == 2
    assert results[0].answer == ""
    assert results[0].correct is False
    assert results[0].error == "affent turn timed out"
    assert results[1].answer == ""
    assert results[1].correct is False
    assert results[1].validation_method == "wallclock"
    assert trajectory[1]["type"] == "question"
    assert trajectory[1]["infra_error"] == "affent turn timed out"
    assert trajectory[2]["stop_reason"] == "unanswered_after_wallclock"


def test_run_affent_agent_keeps_wallclock_invalid_before_questions(
    tmp_path, monkeypatch,
):
    calls = []

    def fake_turn(**kwargs):
        calls.append(kwargs["prompt"])
        return _affent_turn(
            error="affent turn timed out",
        )

    _patch_affent_runner(monkeypatch, fake_turn)
    stream = [
        _ingest_event("Alice", "engineer"),
        _question_event("First?", "one", "Alice"),
    ]

    results, writes_used, stored, eval_error, trajectory = run_affent_agent(
        model="model",
        stream=stream,
        write_budget=2,
        api_base="http://example/v1",
        api_key="key",
        workspace=str(tmp_path / "workspace"),
        quiet=True,
    )

    assert results == []
    assert writes_used == 0
    assert stored == []
    assert eval_error == "affent turn timed out"
    assert len(calls) == 1
    assert [event["type"] for event in trajectory] == ["system", "ingest"]


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
