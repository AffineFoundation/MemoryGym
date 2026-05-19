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
from memorygym.config import get_api_config
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

Rules:
- Documents contain more entities than your budget allows; be selective.
- Corrections must update affected stored memory with action="replace" when possible.
- Questions must be answered directly from the persistent memory snapshot in your system prompt.
- For questions, do not call tools unless you are updating memory; answer in the final assistant message.
- If the answer is not in memory, answer exactly: I don't have enough information.
- Do not use unstored conversation context as memory.
"""

_MEMORY_DELIM = "\n§\n"
_AFFENT_MEMORY_REL = Path(".affent") / "MEMORY.md"


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


def _memory_path(workspace: Path) -> Path:
    return workspace / _AFFENT_MEMORY_REL


def _read_affent_memory_entries(workspace: Path) -> list[str]:
    path = _memory_path(workspace)
    if not path.exists():
        return []
    text = path.read_text().strip()
    if not text:
        return []
    return [p.strip() for p in text.split(_MEMORY_DELIM) if p.strip()]


def _write_affent_memory_entries(workspace: Path, entries: list[str]) -> None:
    path = _memory_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_MEMORY_DELIM.join(entries))


def _stored_contents(workspace: Path) -> list[str]:
    state = _load_memory_state(workspace)
    return [
        e.get("content", "")
        for e in state.get("entries", [])
        if not e.get("deleted") and e.get("content")
    ]


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


def _run_affent_turn(
    *,
    affent_bin: str,
    workspace: Path,
    model: str,
    base_url: str,
    api_key: str,
    session_id: str,
    prompt: str,
    system_prompt: str,
    max_turns: int = 8,
    timeout: float | None = None,
    allow_max_turns_with_tools: bool = False,
) -> _AffentTurn:
    if timeout is not None and timeout <= 0:
        return _AffentTurn(error="affent turn skipped: no wallclock remaining")
    trace_path = workspace / "traces" / f"{time.time_ns()}.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    affent_call_timeout = os.environ.get("MEMORYGYM_AFFENT_CALL_TIMEOUT", "").strip()
    affent_retries = os.environ.get("MEMORYGYM_AFFENT_RETRY_TRANSIENT", "").strip()
    cmd = [
        affent_bin, "run",
        "--workspace", str(workspace),
        "--model", model,
        "--base-url", base_url,
        "--prompt", "-",
        "--session-id", session_id,
        "--memory-only",
        "--max-turns", str(max_turns),
        "--trace", str(trace_path),
        "--trace-skip-deltas",
        "--quiet",
        "--system-prompt", system_prompt,
    ]
    if affent_call_timeout:
        cmd.extend(["--max-call-timeout", affent_call_timeout])
    if affent_retries:
        cmd.extend(["--retry-transient", affent_retries])
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


def _tool_result_ok(result: str | None) -> bool:
    if not result:
        return False
    if result.startswith("[tool] "):
        result = result[len("[tool] "):]
    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        return False
    return bool(data.get("ok"))


def _find_unique(entries: list[str], old_text: str) -> int | None:
    hits = [i for i, e in enumerate(entries) if old_text in e]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1 and len({entries[i] for i in hits}) == 1:
        return hits[0]
    return None


def _apply_memory_budget(
    workspace: Path,
    before_entries: list[str],
    turns: list[dict],
    budget: MemoryBudget,
    *,
    free_replace: bool = False,
) -> int:
    """Replay affent memory calls under MemoryGym's write budget.

    affent is a real agent and does not know MemoryGym's write budget.  The
    benchmark enforces the budget here by replaying successful memory tool
    calls and overwriting the workspace memory with the accepted state.
    """
    entries = list(before_entries)
    writes = 0
    for turn in turns:
        calls = turn.get("tool_calls", [])
        results = turn.get("tool_results", [])
        for i, call in enumerate(calls):
            if call.get("name") != "memory":
                continue
            args = call.get("arguments", {})
            if args.get("target", "memory") != "memory":
                continue
            if not _tool_result_ok(results[i] if i < len(results) else None):
                continue

            action = args.get("action")
            costs_write = not (free_replace and action in ("replace", "remove"))
            if costs_write and not budget.can_write():
                continue
            if action == "add":
                content = str(args.get("content", "")).strip()
                if not content or content in entries:
                    continue
                entries.append(content)
            elif action == "replace":
                old = str(args.get("old_text", "")).strip()
                content = str(args.get("content", "")).strip()
                idx = _find_unique(entries, old)
                if idx is None or not content:
                    continue
                entries[idx] = content
            elif action == "remove":
                old = str(args.get("old_text", "")).strip()
                idx = _find_unique(entries, old)
                if idx is None:
                    continue
                del entries[idx]
            else:
                continue

            if costs_write:
                budget.consume_write()
                writes += 1

    _write_affent_memory_entries(workspace, entries)
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
    workspace_path = Path(workspace) if workspace else Path(tempfile.mkdtemp(prefix="memorygym_affent_"))
    workspace_path.mkdir(parents=True, exist_ok=True)
    system_prompt = AFFENT_MEMORY_SYSTEM_PROMPT.format(budget=write_budget)
    budget = MemoryBudget(total_writes=write_budget)
    judge_key = os.environ.get("CHUTES_API_KEY") or cfg.api_key
    judge_client = OpenAI(api_key=judge_key, base_url="https://llm.chutes.ai/v1")

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
                before_entries = _read_affent_memory_entries(workspace_path)
                turn = _run_affent_turn(
                    affent_bin=affentctl, workspace=workspace_path,
                    model=model, base_url=cfg.api_url, api_key=cfg.api_key,
                    session_id=f"memorygym_{seed}_{event_idx}", prompt=content,
                    system_prompt=system_prompt,
                    max_turns=1,
                    allow_max_turns_with_tools=True,
                    timeout=(deadline - time.time()) if deadline else None,
                )
                turn.writes = _apply_memory_budget(
                    workspace_path, before_entries, turn.turns, budget)
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
                before_entries = _read_affent_memory_entries(workspace_path)
                turn = _run_affent_turn(
                    affent_bin=affentctl, workspace=workspace_path,
                    model=model, base_url=cfg.api_url, api_key=cfg.api_key,
                    session_id=f"memorygym_{seed}_{event_idx}", prompt=content,
                    system_prompt=system_prompt,
                    max_turns=3,
                    allow_max_turns_with_tools=True,
                    timeout=(deadline - time.time()) if deadline else None,
                )
                turn.writes = _apply_memory_budget(
                    workspace_path, before_entries, turn.turns, budget,
                    free_replace=True,
                )
                chain = _extract_action_chain(turn.turns)
                new_val = str(event.get("new_val", "?"))
                correction_ok = any(
                    c.get("name") == "memory"
                    and c.get("arguments", {}).get("action") == "replace"
                    and new_val in str(c.get("arguments", {}).get("content", ""))
                    and i < len(t.get("tool_results", []))
                    and _tool_result_ok(str(t.get("tool_results", [])[i]))
                    for t in turn.turns
                    for i, c in enumerate(t.get("tool_calls", []))
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
                    "Answer directly from your persistent memory snapshot. "
                    "Do not call tools for answering. If the answer is not in memory, "
                    "answer exactly: I don't have enough information."
                )
                before_entries = _read_affent_memory_entries(workspace_path)
                turn = _run_affent_turn(
                    affent_bin=affentctl, workspace=workspace_path,
                    model=model, base_url=cfg.api_url, api_key=cfg.api_key,
                    session_id=f"memorygym_{seed}_{event_idx}", prompt=content,
                    system_prompt=system_prompt,
                    timeout=(deadline - time.time()) if deadline else None,
                )
                turn.writes = _apply_memory_budget(
                    workspace_path, before_entries, turn.turns, budget)
                answer = turn.answer or ""
                gt = str(event["answer"])
                ok, reason = validate_with_fallback(
                    answer, gt, competency, question=question_text,
                    judge_fn=None,
                )
                if not ok and competency != "abstention":
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
        try:
            judge_client.close()
        except Exception:
            pass
