"""MemoryGym runner backed by the affent agent loop.

This adapter drives ``affentctl run`` once per stream event while reusing the
same affent session and persistent memory state in a workspace.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from memorygym.agents._tool_helpers import (
    budget_bar as _budget_bar,
    extract_action_chain as _extract_action_chain,
    format_documents as _format_documents,
)
from memorygym.agents.stream_agent import AgentResult
from memorygym.config import QWEN_FALLBACK_BASE_URL, get_api_config
from memorygym.evaluation.llm_judge import llm_judge_validate_sync
from memorygym.evaluation.validators import validate_with_fallback
from memorygym.memory.budget import MemoryBudget

load_dotenv()


AFFENT_MEMORY_SYSTEM_PROMPT = """You are participating in a memory management evaluation.
You have one persistent memory tool named memory, and the evaluation write budget is {budget} total memory mutations.

Use the memory tool with target="memory":
- action="add" to store concise high-value facts from document events.
- action="replace" to update stale facts during correction events.
- action="remove" only when a stored entry is clearly obsolete.

Store entity facts in compact records like: EntityName | attr: value, attr: value.
Use affent's topic memory naturally: choose durable topic names when they help
organize information, and use topic="core" only for facts that must always be
in the prompt.

Rules:
- Documents contain more entities than your budget allows; be selective.
- Corrections must update affected stored memory with action="replace" when possible.
- Questions are real user interactions: answer from persistent memory and the
  current question, and maintain memory when it improves future usefulness.
- If the answer is not in memory, answer exactly: I don't have enough information.
- Do not use hidden metadata, external sources, or unstored document context as
  factual memory.
"""

_MEMORY_DELIM = "\n§\n"
_AFFENT_MEMORY_DIR_REL = Path(".affent") / "memory"
_AFFENT_USER_REL = Path(".affent") / "USER.md"
_TIMESTAMP_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\]\n")
_TOPIC_RE = re.compile(r"[^a-z0-9_-]+")


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL)


@dataclass
class _AffentTurn:
    answer: str | None = None
    final_text: str = ""
    writes: int = 0
    searches: int = 0
    api_calls: int = 0
    elapsed: float = 0.0
    error: str | None = None
    turns: list[dict] = field(default_factory=list)


def _resolve_affentctl(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get("AFFENTCTL_BIN")
    if candidate:
        path = shutil.which(candidate) or candidate
        if Path(path).exists():
            return path
        raise FileNotFoundError(f"affentctl not found: {candidate}")

    path_candidate = shutil.which("affentctl")
    if path_candidate:
        return path_candidate

    repo = Path(__file__).resolve().parents[3] / "affent"
    built = repo / "affentctl"
    if built.exists():
        return str(built)
    go_bin = shutil.which("go")
    if go_bin is None:
        local_go = Path.home() / ".local" / "go-toolchain" / "go" / "bin" / "go"
        if local_go.exists():
            go_bin = str(local_go)
    if go_bin is None:
        raise FileNotFoundError(
            "affentctl was not provided and Go is not available to build it. "
            "Set --affent-bin or AFFENTCTL_BIN to a built affentctl binary."
        )

    out = Path(tempfile.gettempdir()) / "memorygym-affentctl"
    cmd = [go_bin, "build", "-o", str(out), "./cmd/affentctl"]
    try:
        subprocess.run(
            cmd, cwd=repo, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "affentctl was not provided and Go is not available to build it. "
            "Set --affent-bin or AFFENTCTL_BIN to a built affentctl binary."
        ) from exc
    return str(out)


def _load_memory_state(workspace: Path) -> dict[str, Any]:
    entries = _read_affent_memory_entries(workspace)
    return {
        "writes_used": 0,
        "entries": [{"id": f"mem_{i+1}", "content": e} for i, e in enumerate(entries)],
    }


def _memory_dir(workspace: Path) -> Path:
    return workspace / _AFFENT_MEMORY_DIR_REL


def _memory_user_path(workspace: Path) -> Path:
    return workspace / _AFFENT_USER_REL


def _clear_affent_user_memory(workspace: Path) -> None:
    path = _memory_user_path(workspace)
    path.unlink(missing_ok=True)
    Path(str(path) + ".lock").unlink(missing_ok=True)


def _read_memory_file(path: Path) -> list[str]:
    if not path.exists() or path.is_dir():
        return []
    text = path.read_text().strip()
    if not text:
        return []
    entries = []
    for part in text.split(_MEMORY_DELIM):
        content = _TIMESTAMP_RE.sub("", part.strip()).strip()
        if content:
            entries.append(content)
    return entries


def _normalize_affent_topic(topic: str | None) -> str:
    topic = (topic or "").strip()
    if not topic:
        return "general"
    if topic == "core":
        return "core"
    normalized = _TOPIC_RE.sub("", topic.lower())
    return normalized or "general"


def _read_affent_memory_state(workspace: Path) -> list[dict[str, str]]:
    """Read affent workspace memory from the v2 topic layout."""
    state: list[dict[str, str]] = []
    mem_dir = _memory_dir(workspace)
    for content in _read_memory_file(mem_dir / "core.md"):
        state.append({"topic": "core", "content": content})
    topics_dir = mem_dir / "topics"
    if topics_dir.exists():
        for path in sorted(topics_dir.glob("*.md")):
            topic = _normalize_affent_topic(path.stem)
            for content in _read_memory_file(path):
                state.append({"topic": topic, "content": content})
    return state


def _read_affent_memory_entries(workspace: Path) -> list[str]:
    """Return user-visible memory contents for MemoryGym scoring."""
    return [entry["content"] for entry in _read_affent_memory_state(workspace)]


def _write_memory_file_atomic(path: Path, entries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".mem-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(_MEMORY_DELIM.join(entries))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _write_affent_memory_state(workspace: Path, state: list[dict[str, str]]) -> None:
    """Write the MemoryGym-accepted state using affent's v2 layout.

    The evaluated agent may organize memory into affent topics. MemoryGym
    replays successful mutations against its write budget, then rewrites the
    workspace memory to that accepted state so later turns cannot benefit from
    over-budget mutations that affent already executed on disk.
    """
    mem_dir = _memory_dir(workspace)
    if mem_dir.exists():
        shutil.rmtree(mem_dir)

    by_topic: dict[str, list[str]] = {}
    for entry in state:
        content = entry.get("content", "").strip()
        if not content:
            continue
        topic = _normalize_affent_topic(entry.get("topic"))
        by_topic.setdefault(topic, []).append(content)

    for topic, entries in sorted(by_topic.items()):
        if topic == "core":
            path = mem_dir / "core.md"
        else:
            path = mem_dir / "topics" / f"{topic}.md"
        _write_memory_file_atomic(path, entries)


def _stored_contents(workspace: Path) -> list[str]:
    state = _load_memory_state(workspace)
    return [
        e.get("content", "")
        for e in state.get("entries", [])
        if not e.get("deleted") and e.get("content")
    ]


def _new_judge_client() -> OpenAI | None:
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    if dashscope_key:
        return OpenAI(api_key=dashscope_key, base_url=QWEN_FALLBACK_BASE_URL)
    key = os.environ.get("CHUTES_API_KEY", "").strip()
    if not key:
        return None
    return OpenAI(api_key=key, base_url="https://llm.chutes.ai/v1")


def _parse_trace(
    trace_path: Path,
    *,
    allow_max_turns_with_tools: bool = False,
) -> _AffentTurn:
    turn = _AffentTurn()
    tool_calls: list[dict] = []
    tool_results: list[str] = []
    if not trace_path.exists():
        turn.error = "affent trace was not created"
        return turn

    for line in trace_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = ev.get("type")
        data = ev.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        if etype == "tool.request":
            name = data.get("tool", "")
            args = data.get("args", {}) or {}
            tool_calls.append({"name": name, "arguments": args})
            if name == "memory":
                action = str(args.get("action", ""))
                if action in ("add", "replace", "remove"):
                    turn.writes += 1
        elif etype == "tool.result":
            # Prefer the full, untruncated `result` field added in affent's
            # SSE schema; fall back to `result_summary` for older binaries.
            # result_summary is a UI-preview capped at 4 KiB and may carry
            # truncated (unparseable) JSON for large memory responses.
            full = data.get("result")
            if full is None:
                full = data.get("result_summary", "")
            tool_results.append(f"[tool] {full}")
        elif etype == "message.done":
            turn.final_text = _strip_think(str(data.get("text", ""))).strip()
        elif etype == "usage":
            turn.api_calls += 1
        elif etype == "error":
            turn.error = str(data.get("message", "affent error"))
        elif etype == "turn.end" and data.get("reason") not in (None, "completed"):
            reason = data.get("reason")
            if not (allow_max_turns_with_tools and reason == "max_turns" and tool_calls):
                turn.error = f"affent turn ended: {reason}"

    if turn.answer is None and turn.final_text:
        turn.answer = turn.final_text.strip()
    if turn.api_calls == 0 and (tool_calls or turn.final_text):
        turn.api_calls = 1
    if tool_calls or tool_results or turn.answer is not None:
        detail = {
            "turn": 0,
            "role": "assistant",
            "content": turn.final_text,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
        }
        if turn.answer is not None:
            detail["answer"] = turn.answer
        turn.turns.append(detail)
    return turn


def _write_eval_config(workspace: Path, system_prompt: str) -> Path:
    """Write a JSON config for affent's --config flag.

    Centralizes all fixed eval settings so the CLI only carries
    per-turn dynamic arguments (prompt, session-id, max-turns, trace).
    """
    cfg = {
        "eval_mode": True,
        "memory": {
            "only": True,
            "user_store": str(_memory_user_path(workspace)),
        },
        "system_prompt": system_prompt,
        "temperature": "0",
        "quiet": True,
        "trace_skip_deltas": True,
        "max_call_timeout": "5m",
    }
    path = workspace / ".memorygym-eval-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg))
    return path


def _run_affent_turn(
    *,
    affent_bin: str,
    workspace: Path,
    model: str,
    api_key: str,
    base_url: str,
    config_path: Path,
    session_id: str,
    prompt: str,
    max_turns: int = 8,
    timeout: float | None = None,
    allow_max_turns_with_tools: bool = False,
) -> _AffentTurn:
    if timeout is not None and timeout <= 0:
        return _AffentTurn(error="affent turn skipped: no wallclock remaining")
    _clear_affent_user_memory(workspace)
    trace_path = workspace / "traces" / f"{time.time_ns()}.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        affent_bin, "run",
        "--config", str(config_path),
        "--workspace", str(workspace),
        "--model", model,
        "--base-url", base_url,
        "--prompt", "-",
        "--session-id", session_id,
        "--max-turns", str(max_turns),
        "--trace", str(trace_path),
    ]
    t0 = time.time()
    try:
        env = os.environ.copy()
        env["AFFENTCTL_API_KEY"] = api_key
        env["XDG_CONFIG_HOME"] = str(workspace / ".xdg")
        proc = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _AffentTurn(error="affent turn timed out", elapsed=time.time() - t0)

    turn = _parse_trace(
        trace_path,
        allow_max_turns_with_tools=allow_max_turns_with_tools,
    )
    turn.elapsed = time.time() - t0
    if (
        proc.returncode != 0
        and turn.error is None
        and not (allow_max_turns_with_tools and proc.returncode == 2 and turn.turns)
    ):
        turn.error = f"affentctl exited {proc.returncode}: {proc.stderr[-300:]}"
    if turn.final_text == "" and proc.stdout.strip():
        turn.final_text = proc.stdout.strip()
        if turn.answer is None:
            turn.answer = turn.final_text
    return turn


def _correction_applied(turns: list[dict], entity_name: str, new_val: str) -> bool:
    """Decide whether a correction event was successfully applied.

    Returns True iff at least one memory.replace call satisfies all of:
    old_text contains entity_name, content contains new_val, and the
    tool_result reports ok=true.
    """
    if not entity_name:
        return False
    for t in turns:
        calls = t.get("tool_calls", [])
        results = t.get("tool_results", [])
        for i, c in enumerate(calls):
            if c.get("name") != "memory":
                continue
            args = c.get("arguments", {})
            if args.get("action") != "replace":
                continue
            if entity_name not in str(args.get("old_text", "")):
                continue
            if new_val not in str(args.get("content", "")):
                continue
            if i >= len(results):
                continue
            if not _tool_result_ok(str(results[i])):
                continue
            return True
    return False


def _tool_result_ok(result: str | None) -> bool:
    data = _tool_result_data(result)
    return bool(data and data.get("ok"))


def _tool_result_data(result: str | None) -> dict[str, Any] | None:
    if not result:
        return None
    if result.startswith("[tool] "):
        result = result[len("[tool] "):]
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return None


def _find_unique(
    entries: list[dict[str, str]],
    old_text: str,
    topic: str,
) -> int | None:
    hits = [
        i for i, e in enumerate(entries)
        if e.get("topic") == topic and old_text in e.get("content", "")
    ]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1 and len({entries[i].get("content", "") for i in hits}) == 1:
        return hits[0]
    return None


def _apply_memory_budget(
    workspace: Path,
    before_state: list[dict[str, str]],
    turns: list[dict],
    budget: MemoryBudget,
    *,
    free_replace: bool = False,
) -> int:
    """Replay affent memory calls under MemoryGym's write budget.

    The benchmark enforces the budget here by replaying successful
    memory tool calls and overwriting the workspace memory with the
    accepted state. When the resulting entries equal before_state,
    skips the disk write.
    """
    entries = [dict(entry) for entry in before_state]
    writes = 0
    saw_memory_call = False
    for turn in turns:
        calls = turn.get("tool_calls", [])
        results = turn.get("tool_results", [])
        for i, call in enumerate(calls):
            if call.get("name") != "memory":
                continue
            saw_memory_call = True
            args = call.get("arguments", {})
            if args.get("target", "memory") != "memory":
                continue
            result = _tool_result_data(results[i] if i < len(results) else None)
            if not result or not result.get("ok"):
                continue

            action = args.get("action")
            topic = _normalize_affent_topic(
                str(result.get("topic") or args.get("topic") or ""))
            costs_write = not (free_replace and action in ("replace", "remove"))
            if costs_write and not budget.can_write():
                continue
            if action == "add":
                content = str(args.get("content", "")).strip()
                if not content:
                    continue
                if any(
                    e.get("topic") == topic and e.get("content") == content
                    for e in entries
                ):
                    continue
                entries.append({"topic": topic, "content": content})
            elif action == "replace":
                old = str(args.get("old_text", "")).strip()
                content = str(args.get("content", "")).strip()
                idx = _find_unique(entries, old, topic)
                if idx is None or not content:
                    continue
                entries[idx] = {"topic": topic, "content": content}
            elif action == "remove":
                old = str(args.get("old_text", "")).strip()
                idx = _find_unique(entries, old, topic)
                if idx is None:
                    continue
                del entries[idx]
            else:
                continue

            if costs_write:
                budget.consume_write()
                writes += 1

    _clear_affent_user_memory(workspace)
    if saw_memory_call or entries != before_state:
        _write_affent_memory_state(workspace, entries)
    return writes


def run_affent_agent(
    model: str,
    stream: list[dict],
    write_budget: int = 30,
    api_base: str | None = None,
    api_key: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
    world: Any = None,
    template: Any = None,
    seed: int = 0,
    wallclock_budget: float | None = None,
    affent_bin: str | None = None,
    workspace: str | None = None,
) -> tuple[list[AgentResult], int, list[str], str | None, list[dict]]:
    """Run MemoryGym using affent as the evaluation agent."""
    cfg = get_api_config(api_key=api_key, api_url=api_base)
    affentctl = _resolve_affentctl(affent_bin)
    owns_workspace = workspace is None
    workspace_path = Path(workspace) if workspace else Path(tempfile.mkdtemp(prefix="memorygym_affent_"))
    workspace_path.mkdir(parents=True, exist_ok=True)
    system_prompt = AFFENT_MEMORY_SYSTEM_PROMPT.format(budget=write_budget)
    budget = MemoryBudget(total_writes=write_budget)
    judge_client = _new_judge_client()
    eval_config = _write_eval_config(workspace_path, system_prompt)

    results: list[AgentResult] = []
    trajectory: list[dict] = [{"event_idx": -1, "type": "system", "content": system_prompt}]
    eval_error: str | None = None
    run_t0 = time.time()
    deadline = run_t0 + wallclock_budget if wallclock_budget else None
    total_events = len(stream)
    entities_seen = 0
    total_entities = sum(len(e.get("entity_names", [])) for e in stream if e["type"] == "ingest")

    try:
        for event_idx, event in enumerate(stream):
            if deadline and time.time() >= deadline:
                eval_error = f"wallclock_exhausted at event {event_idx}/{total_events}"
                break
            event_type = event["type"]
            label = f"[{event_idx+1}/{total_events}]"

            if event_type == "session_break":
                trajectory.append({
                    "event_idx": event_idx,
                    "type": "session_break",
                    "session_id": event.get("session_id", 2),
                    "total_sessions": event.get("total_sessions", 2),
                })
                continue

            if event_type == "ingest":
                entity_names = event.get("entity_names", [])
                if not quiet:
                    print(f"  {label} AFFENT INGEST {len(entity_names)} entities")
                docs_text = _format_documents(event["documents"])
                content = (
                    f"=== Event {event_idx+1}/{total_events} [DOCUMENTS] ===\n\n"
                    f"Budget: {write_budget - budget.writes_used}/{write_budget} writes remaining. "
                    f"Entities seen so far: {entities_seen}/{total_entities}.\n\n"
                    f"Documents:\n{docs_text}\n\n"
                    "No question. Store important entity data using the memory tool "
                    "with action=\"add\" and target=\"memory\". Stop when the budget is exhausted."
                )
                entities_seen += len(entity_names)
                before_state = _read_affent_memory_state(workspace_path)
                turn = _run_affent_turn(
                    affent_bin=affentctl, workspace=workspace_path,
                    model=model, api_key=cfg.api_key, base_url=cfg.api_url,
                    config_path=eval_config,
                    session_id=f"memorygym_{seed}_{event_idx}", prompt=content,
                    max_turns=1,
                    allow_max_turns_with_tools=True,
                    timeout=(deadline - time.time()) if deadline else None,
                )
                turn.writes = _apply_memory_budget(
                    workspace_path, before_state, turn.turns, budget)
                if not quiet:
                    print(f"           {turn.api_calls} calls, {turn.elapsed:.1f}s  {_budget_bar(budget.writes_used, write_budget)}")
                trajectory.append({
                    "event_idx": event_idx,
                    "type": "ingest",
                    "entity_names": entity_names,
                    "content": content,
                    "writes": turn.writes,
                    "searches": turn.searches,
                    "api_calls": turn.api_calls,
                    "budget_remaining": budget.remaining(),
                    "turns": turn.turns,
                    "infra_error": turn.error,
                })
                if turn.error:
                    eval_error = turn.error
                    break

            elif event_type == "correction":
                if not quiet:
                    print(f"  {label} AFFENT CORRECT {event['entity_name']}.{event['attr']}")
                content = (
                    f"=== Event {event_idx+1}/{total_events} [CORRECTION] ===\n\n"
                    f"Correction Notice:\n{event['notice']}\n\n"
                    f"Entity: {event['entity_name']}\n"
                    f"Old value: {event.get('old_val', '?')}\n"
                    f"New value: {event.get('new_val', '?')}\n\n"
                    "If this entity is in memory, use the memory tool with "
                    "action=\"replace\" and target=\"memory\" to update it. "
                    "Replacement edits are free for this event."
                )
                before_state = _read_affent_memory_state(workspace_path)
                turn = _run_affent_turn(
                    affent_bin=affentctl, workspace=workspace_path,
                    model=model, api_key=cfg.api_key, base_url=cfg.api_url,
                    config_path=eval_config,
                    session_id=f"memorygym_{seed}_{event_idx}", prompt=content,
                    max_turns=3,
                    allow_max_turns_with_tools=True,
                    timeout=(deadline - time.time()) if deadline else None,
                )
                turn.writes = _apply_memory_budget(
                    workspace_path, before_state, turn.turns, budget,
                    free_replace=True,
                )
                chain = _extract_action_chain(turn.turns)
                correction_ok = _correction_applied(
                    turn.turns,
                    str(event.get("entity_name", "")),
                    str(event.get("new_val", "?")),
                )
                trajectory.append({
                    "event_idx": event_idx,
                    "type": "correction",
                    "entity_name": event["entity_name"],
                    "attr": event["attr"],
                    "old_val": event.get("old_val", "?"),
                    "new_val": event.get("new_val", "?"),
                    "content": content,
                    "writes": turn.writes,
                    "searches": turn.searches,
                    "api_calls": turn.api_calls,
                    "correction_applied": correction_ok,
                    "turns": turn.turns,
                    "infra_error": turn.error,
                })
                if not quiet:
                    mark = "OK" if correction_ok else "MISS"
                    print(f"           [{mark}] {chain}  {_budget_bar(budget.writes_used, write_budget)}")
                if turn.error:
                    eval_error = turn.error
                    break

            elif event_type == "question":
                if world is not None and template is not None:
                    event = template.maybe_replace_comprehension(
                        event, world, _stored_contents(workspace_path),
                        rng_seed=seed + event_idx,
                    )
                competency = event["competency"]
                question_text = event["question"]
                if not quiet:
                    print(f"  {label} AFFENT QUESTION [{competency}] {question_text[:70]}")
                content = (
                    f"=== Event {event_idx+1}/{total_events} [QUESTION] ===\n\n"
                    f"Question:\n{question_text}\n\n"
                    "Answer using only your persistent memory and this question. "
                    "You may maintain memory if it helps future interactions. "
                    "Do not use hidden metadata, external sources, or unstored "
                    "document context. If the answer is not in memory, answer "
                    "exactly: I don't have enough information."
                )
                before_state = _read_affent_memory_state(workspace_path)
                turn = _run_affent_turn(
                    affent_bin=affentctl, workspace=workspace_path,
                    model=model, api_key=cfg.api_key, base_url=cfg.api_url,
                    config_path=eval_config,
                    session_id=f"memorygym_{seed}_{event_idx}", prompt=content,
                    timeout=(deadline - time.time()) if deadline else None,
                )
                turn.writes = _apply_memory_budget(
                    workspace_path, before_state, turn.turns, budget)
                answer = turn.answer or ""
                gt = str(event["answer"])
                ok, reason = validate_with_fallback(
                    answer, gt, competency, question=question_text,
                    judge_fn=None,
                )
                if not ok and competency != "abstention" and judge_client is not None:
                    try:
                        ok, judge_reason = llm_judge_validate_sync(
                            judge_client, question_text, gt, answer, competency)
                        reason = f"judge:{judge_reason}"
                    except Exception as exc:
                        reason = f"judge:failed({exc})"
                via = reason.split(":")[0]
                if not quiet:
                    print(f"           [{'+' if ok else '-'}] GT={gt[:50]} A={answer[:50]} via={via}")
                results.append(AgentResult(
                    question=question_text,
                    answer=answer,
                    ground_truth=gt,
                    competency=competency,
                    purpose=event.get("purpose", ""),
                    correct=ok,
                    n_writes=turn.writes,
                    n_searches=turn.searches,
                    required_entities=event.get("required_entities", []),
                    validation_method=via,
                    validation_reason=reason,
                    api_calls=turn.api_calls,
                    elapsed=turn.elapsed,
                    error=turn.error,
                ))
                trajectory.append({
                    "event_idx": event_idx,
                    "type": "question",
                    "competency": competency,
                    "purpose": event.get("purpose", ""),
                    "question": question_text,
                    "ground_truth": gt,
                    "agent_answer": answer,
                    "correct": ok,
                    "content": content,
                    "writes": turn.writes,
                    "searches": turn.searches,
                    "api_calls": turn.api_calls,
                    "elapsed": round(turn.elapsed, 2),
                    "turns": turn.turns,
                    "infra_error": turn.error,
                })
                if turn.error:
                    eval_error = turn.error
                    break

        stored = _stored_contents(workspace_path)
        return results, budget.writes_used, stored, eval_error, trajectory
    finally:
        if judge_client is not None:
            try:
                judge_client.close()
            except Exception:
                pass
        if owns_workspace:
            shutil.rmtree(workspace_path, ignore_errors=True)
