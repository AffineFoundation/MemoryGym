"""LLM agent for WorldTemplate stream evaluation.

Processes interleaved event streams (ingest/correction/question) using
text-based tool calling via OpenAI-compatible API.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from memorygym.agents._tool_helpers import (
    budget_bar as _budget_bar,
    execute_tool as _execute_tool,
    extract_action_chain as _extract_action_chain,
    extract_search_queries as _extract_search_queries,
    extract_stored_keys as _extract_stored_keys,
    format_documents as _format_documents,
    MemoryBackend,
)

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from memorygym.config import get_api_config
from memorygym.evaluation.llm_judge import llm_judge_validate_sync
from memorygym.evaluation.validators import validate_with_fallback
from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.memory.budget import MemoryBudget


SYSTEM_PROMPT = """You are participating in a memory management evaluation.
Write budget: {budget} total writes. Be selective — you'll see more entities than you can store.

## Event Types
1. DOCUMENTS: Entity data to read and store selectively.
2. CORRECTIONS: Updated data. You MUST update stored memories.
3. QUESTIONS: Answer from stored memories only.

## Tools

Call tools by outputting JSON blocks:

**Write** — Append to your memory file (costs 1 write, budget: {budget}):
<tool_call>{{"name": "Write", "arguments": {{"content": "info to store"}}}}</tool_call>

**Edit** — Update existing content in your memory file when data changes (costs 1 write). Use old_text/new_text to replace outdated values:
<tool_call>{{"name": "Edit", "arguments": {{"old_text": "text to find", "new_text": "replacement text"}}}}</tool_call>

**Read** — Read your memory file (free):
<tool_call>{{"name": "Read", "arguments": {{}}}}</tool_call>

**memory_search** — Semantic search over your memory (free):
<tool_call>{{"name": "memory_search", "arguments": {{"query": "entity name"}}}}</tool_call>

**submit_answer** — Submit your final answer:
<tool_call>{{"name": "submit_answer", "arguments": {{"answer": "your answer"}}}}</tool_call>

## Memory Budget
- You have limited write operations — plan your usage carefully
- Each Write or Edit counts against your budget

## Answering Questions
- Search by entity name, then submit_answer with the value
- For comparison/synthesis: answer as "EntityName (value)"
- If data not in memory: submit "I don't have enough information"
- Do NOT guess or fabricate values
- ALWAYS call submit_answer for every question
"""

_TOOL_CALL_RE = re.compile(
    r"<(?:tool_call|function_call)>\s*(\{.*?\})\s*</(?:tool_call|function_call)>",
    re.DOTALL,
)

# Valid tool names for bare-JSON detection
_KNOWN_TOOLS = {
    "Write", "Edit", "Read", "memory_search", "submit_answer",
    # Legacy names (backward compatibility during transition)
    "memory_store", "memory_get", "memory_forget", "memory_list",
}

# Markdown code block: ```json\n{...}\n``` or ```\n{...}\n```
_CODE_BLOCK_RE = re.compile(
    r"```(?:json)?\s*\n(\{.*?\})\s*\n```", re.DOTALL,
)

# Bare JSON: {"name": "...", "arguments": {...}}  (no XML wrapper)
_BARE_JSON_RE = re.compile(
    r'\{[^{}]*"name"\s*:\s*"[^"]+?"[^{}]*"arguments"\s*:\s*\{[^{}]*\}[^{}]*\}',
)


@dataclass
class AgentResult:
    """Result of processing one question event."""
    question: str
    answer: str
    ground_truth: str
    competency: str
    purpose: str
    correct: bool
    n_writes: int
    n_searches: int
    required_entities: list[str] = field(default_factory=list)
    validation_method: str = ""       # "rule" or "judge"
    validation_reason: str = ""       # detailed reason from validator/judge
    api_calls: int = 0                # API calls for this question
    elapsed: float = 0.0              # seconds for this question
    retries: int = 0                  # transient retries during this question
    error: str | None = None          # non-None if eval model failed


def _extract_tool_calls(text: str) -> list[dict]:
    """Extract tool calls from text.

    Supports (in priority order):
    1. <tool_call>/<function_call> XML tags
    2. Markdown code blocks (```json ... ```)
    3. Bare JSON with "name"/"arguments" keys
    """
    calls = []
    # 1) Try XML-wrapped format first (<tool_call> or <function_call>)
    for match in _TOOL_CALL_RE.finditer(text):
        try:
            call = json.loads(match.group(1))
            if call.get("name") in _KNOWN_TOOLS:
                calls.append(call)
        except json.JSONDecodeError:
            continue
    if calls:
        return calls
    # 2) Try markdown code blocks
    for match in _CODE_BLOCK_RE.finditer(text):
        try:
            call = json.loads(match.group(1))
            if call.get("name") in _KNOWN_TOOLS:
                calls.append(call)
        except json.JSONDecodeError:
            continue
    if calls:
        return calls
    # 3) Fallback: bare JSON (Qwen-style)
    for match in _BARE_JSON_RE.finditer(text):
        try:
            call = json.loads(match.group(0))
            if call.get("name") in _KNOWN_TOOLS:
                calls.append(call)
        except json.JSONDecodeError:
            continue
    return calls



@dataclass
class _LoopStats:
    """Stats from one tool loop invocation."""
    answer: str | None = None
    writes: int = 0
    searches: int = 0
    api_calls: int = 0
    elapsed: float = 0.0
    retries: int = 0
    ctx_trims: int = 0
    error: str | None = None
    turns: list[dict] = field(default_factory=list)  # per-turn detail


def _run_tool_loop(
    client: OpenAI, model: str, messages: list[dict],
    backend: MemoryBackend, budget: MemoryBudget,
    max_turns: int = 10, max_retries: int = 10,
    *, free_edit: bool = False,
) -> _LoopStats:
    """Run text-based tool loop until submit_answer or max_turns.

    Args:
        max_retries: Max consecutive retries for transient eval model errors.
            After this many failures, the loop aborts with stats.error set.
            Judge/infrastructure errors are handled separately (always retry).
    """
    stats = _LoopStats()
    t0 = time.time()

    for turn in range(max_turns):
        # Retry up to max_retries on transient eval model errors.
        # On context overflow, trim intermediate tool messages and retry.
        attempt = 0
        while True:
            try:
                response = client.chat.completions.create(
                    model=model, messages=messages,
                    max_tokens=4096,
                )
                break
            except Exception as e:
                err_str = str(e)
                err_lower = err_str.lower()
                # Context length exceeded → trim messages
                if ("context" in err_lower and "length" in err_lower
                        or "input_tokens" in err_lower
                        or "reduce the length" in err_lower):
                    if len(messages) > 4:
                        messages[2:-2] = []
                        stats.ctx_trims += 1
                        print(" [ctx-trim]", end="", flush=True)
                        continue
                    else:
                        # Context overflow with no room to prune — abstain gracefully
                        stats.answer = "I don't have enough information"
                        response = None
                        break
                transient = ("429" in err_str or "503" in err_str
                             or "capacity" in err_lower
                             or "overloaded" in err_lower
                             or "timeout" in err_lower
                             or "502" in err_str)
                if not transient:
                    raise
                attempt += 1
                stats.retries += 1
                if attempt > max_retries:
                    stats.error = (
                        f"Eval model unreachable after {max_retries} "
                        f"retries: {err_str[:200]}")
                    stats.elapsed = time.time() - t0
                    return stats
                wait = min(2 ** attempt * 5, 60)
                print(f" [retry #{attempt}/{max_retries} in {wait}s]",
                      end="", flush=True)
                time.sleep(wait)
        if response is None:
            break  # context overflow, unrecoverable for this turn
        stats.api_calls += 1
        text = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": text})

        parsed_calls = _extract_tool_calls(text)
        results: list[str] = []
        answer: str | None = None
        writes_before = budget.writes_used
        for call in parsed_calls:
            name = call.get("name", "")
            args = call.get("arguments", {})
            result_text, submitted = _execute_tool(
                name, args, backend, budget, free_edit=free_edit)
            results.append(f"[{name}] {result_text}")
            if submitted is not None:
                answer = submitted
            if name in ("memory_search", "memory_list", "memory_get", "Read"):
                stats.searches += 1
        stats.writes += budget.writes_used - writes_before

        # Capture per-turn detail for trajectory
        turn_detail: dict[str, Any] = {
            "turn": turn,
            "role": "assistant",
            "content": text,
            "tool_calls": [
                {"name": c.get("name"), "arguments": c.get("arguments", {})}
                for c in parsed_calls
            ],
            "tool_results": results,
        }
        if answer is not None:
            turn_detail["answer"] = answer
        stats.turns.append(turn_detail)

        if answer is not None:
            stats.answer = answer
            break

        if not results:
            # If no tool calls and no answer on the first attempt,
            # nudge the model to use submit_answer. This handles
            # models that generate reasoning text (e.g. <think> blocks)
            # without producing tool calls.
            if turn == 0 and answer is None:
                messages.append({
                    "role": "user",
                    "content": (
                        "You must call submit_answer(answer=\"...\") "
                        "with your answer, or "
                        "submit_answer(answer=\"I don't have enough "
                        "information\") if unsure. "
                        "Use memory_search first if needed."
                    ),
                })
                continue
            break

        messages.append({
            "role": "user",
            "content": "Tool results:\n" + "\n".join(results),
        })

    stats.elapsed = time.time() - t0
    return stats


def run_stream_agent(
    model: str,
    stream: list[dict],
    write_budget: int = 30,
    api_base: str | None = None,
    api_key: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
    backend: MemoryBackend | None = None,
    world: Any = None,
    template: Any = None,
    seed: int = 0,
    no_redaction: bool = False,
) -> tuple[list[AgentResult], int, list[dict], str | None, list[dict]]:
    """Run a real LLM agent on a WorldTemplate event stream.

    Args:
        model: Model name (OpenAI-compatible).
        stream: List of events from WorldTemplate.generate_stream().
        write_budget: Total memory writes allowed.
        api_base: API base URL (default: OpenAI).
        api_key: API key (default: from env).
        verbose: Print per-event details (legacy, superseded by default).
        quiet: Minimal output (old-style single-line per event).
        backend: Memory backend (default: ChromaDBBackend).
        world: World instance for adaptive comprehension questions.
        template: WorldTemplate instance for adaptive comprehension questions.
        seed: Random seed for replacement question generation.
        no_redaction: Keep full conversation history (long-context mode).

    Returns:
        (results, writes_used, stored_contents, error_or_none)
    """
    cfg = get_api_config(api_key=api_key, api_url=api_base)
    client = OpenAI(api_key=cfg.api_key, base_url=cfg.api_url)

    # Judge client: same API config (Chutes supports cheap multi-model judging)
    judge_client = OpenAI(api_key=cfg.api_key, base_url=cfg.api_url)

    if backend is None:
        backend = ChromaDBBackend()
    budget = MemoryBudget(total_writes=write_budget)

    total_events = len(stream)
    eval_error: str | None = None
    system_prompt = SYSTEM_PROMPT.format(budget=write_budget)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    results: list[AgentResult] = []
    trajectory: list[dict] = [
        {"event_idx": -1, "type": "system", "content": system_prompt},
    ]
    pending_judge: list[tuple] = []  # (result_idx, question, gt, answer, competency)
    total_api_calls = 0
    run_t0 = time.time()

    # Precompute stream stats for dynamic budget context
    total_entities = sum(
        len(e.get("entity_names", []))
        for e in stream if e["type"] == "ingest"
    )
    n_corrections_total = sum(1 for e in stream if e["type"] == "correction")
    entities_seen = 0

    prev_phase = None  # Track phase transitions for separators
    correction_results: list[dict] = []  # Track correction outcomes

    for event_idx, event in enumerate(stream):
        msg_start = len(messages)
        event_type = event["type"]
        event_label = f"[{event_idx+1}/{total_events}]"

        # Phase separator
        if not quiet and event_type != prev_phase:
            if prev_phase == "ingest" and event_type == "correction":
                print(f"\n  {'─' * 50}")
                print(f"  PHASE: CORRECTIONS ({n_corrections_total} expected)")
                print(f"  {_budget_bar(budget.writes_used, write_budget)}")
                print(f"  {'─' * 50}")
            elif prev_phase in ("ingest", "correction") and event_type == "question":
                # Summarize corrections if any happened
                if correction_results:
                    ok = sum(1 for c in correction_results if c["success"])
                    print(f"  Corrections: {ok}/{len(correction_results)} "
                          f"successfully updated")
                print(f"\n  {'─' * 50}")
                print(f"  PHASE: QUESTIONS")
                print(f"  {_budget_bar(budget.writes_used, write_budget)}")
                stored_entries = backend.list()
                print(f"  Memory: {len(stored_entries)} entries stored")
                print(f"  {'─' * 50}")
            prev_phase = event_type

        if event_type == "session_break":
            session_id = event.get("session_id", 2)
            total_sess = event.get("total_sessions", 2)
            if not quiet:
                print(f"\n  {'═' * 50}")
                print(f"  SESSION BREAK — Starting session "
                      f"{session_id}/{total_sess}")
                print(f"  Context cleared. Memory backend preserved.")
                print(f"  {_budget_bar(budget.writes_used, write_budget)}")
                print(f"  {'═' * 50}\n")
            # Clear conversation context, keep memory backend
            messages = [{"role": "system", "content": system_prompt}]
            trajectory.append({
                "event_idx": event_idx,
                "type": "session_break",
                "session_id": session_id,
                "total_sessions": total_sess,
            })
            prev_phase = None
            continue

        if event_type == "ingest":
            entity_names = event.get("entity_names", [])
            n_ents = len(entity_names)
            if quiet:
                print(f"  {event_label} INGEST  {n_ents} entities ...",
                      end="", flush=True)
            else:
                preview = ", ".join(entity_names[:5])
                if n_ents > 5:
                    preview += f" (+{n_ents - 5} more)"
                print(f"  {event_label} INGEST  {n_ents} entities: "
                      f"{preview}")

            docs_text = _format_documents(event["documents"])
            # Dynamic budget context
            remaining = budget.remaining()
            budget_ctx = (
                f"⚠️ Budget: {remaining}/{write_budget} writes remaining. "
                f"Entities seen so far: {entities_seen} (more may follow). "
                f"Be selective — store what matters most."
            )
            content = (
                f"=== Event {event_idx+1}/{total_events} [DOCUMENTS] ===\n\n"
                f"{budget_ctx}\n\n"
                f"**Documents:**\n{docs_text}\n\n"
                "No question. Store important entity data."
            )
            entities_seen += n_ents
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(client, model, messages, backend, budget)
            total_api_calls += stats.api_calls

            if quiet:
                print(f" {stats.api_calls} calls {stats.elapsed:.1f}s "
                      f"budget={budget.remaining()}")
            else:
                stored_keys = _extract_stored_keys(stats.turns)
                skipped = n_ents - len(stored_keys)
                print(f"           stored {len(stored_keys)}/{n_ents}: "
                      f"{', '.join(stored_keys[:6])}"
                      + (f" (+{len(stored_keys)-6})"
                         if len(stored_keys) > 6 else ""))
                if skipped > 0:
                    print(f"           skipped {skipped} entities")
                print(f"           {stats.api_calls} calls, "
                      f"{stats.elapsed:.1f}s  "
                      f"{_budget_bar(budget.writes_used, write_budget)}")

            trajectory.append({
                "event_idx": event_idx,
                "type": "ingest",
                "entity_names": entity_names,
                "content": content,
                "writes": stats.writes,
                "searches": stats.searches,
                "api_calls": stats.api_calls,
                "budget_remaining": budget.remaining(),
                "turns": stats.turns,
            })
            if stats.error:
                print(f"  ERROR: {stats.error}")
                eval_error = stats.error
                break

        elif event_type == "correction":
            entity_name = event["entity_name"]
            attr = event["attr"]
            old_val = event.get("old_val", "?")
            new_val = event.get("new_val", "?")

            if quiet:
                print(f"  {event_label} CORRECT {entity_name}.{attr} ...",
                      end="", flush=True)
            else:
                print(f"  {event_label} CORRECT {entity_name}.{attr}: "
                      f"{old_val} -> {new_val}")

            content = (
                f"=== Event {event_idx+1}/{total_events} [CORRECTION] ===\n\n"
                f"**Correction Notice:**\n{event['notice']}\n\n"
                f"Entity: {entity_name}\n"
                f"Old value: {old_val}\n"
                f"New value: {new_val}\n\n"
                f"If you stored data about this entity, use memory_search "
                f"to find it and Edit to update. "
                f"Correction edits do not consume your write budget."
            )
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(client, model, messages, backend, budget,
                                   free_edit=True)
            total_api_calls += stats.api_calls

            # Determine if correction was actually applied
            chain = _extract_action_chain(stats.turns)
            did_store = False
            did_edit = False
            did_search = False
            stored_new = False
            for t in stats.turns:
                calls = t.get("tool_calls", [])
                tool_results = t.get("tool_results", [])
                for i, c in enumerate(calls):
                    cname = c.get("name", "")
                    cargs = c.get("arguments", {})
                    result = tool_results[i] if i < len(tool_results) else ""
                    if cname == "memory_search":
                        did_search = True
                    elif cname in ("Write", "memory_store"):
                        # Check result indicates success (not budget exhausted)
                        if "Budget exhausted" not in result:
                            did_store = True
                            if str(new_val) in str(cargs.get("content", "")):
                                stored_new = True
                    elif cname == "Edit":
                        # Check result indicates success (Edited, not rejected)
                        if "Edited." in result:
                            did_edit = True
                            if str(new_val) in str(cargs.get("new_text", "")):
                                stored_new = True

            correction_ok = (did_store or did_edit) and stored_new
            correction_results.append({
                "entity": entity_name, "attr": attr,
                "success": correction_ok,
                "chain": chain,
            })

            if quiet:
                print(f" {stats.api_calls} calls {stats.elapsed:.1f}s "
                      f"budget={budget.remaining()}")
            else:
                mark = "OK" if correction_ok else "MISS"
                print(f"           [{mark}] {chain}")
                if did_store and not stored_new:
                    print(f"           WARNING: stored but with old value")
                print(f"           {stats.api_calls} calls, "
                      f"{stats.elapsed:.1f}s  "
                      f"{_budget_bar(budget.writes_used, write_budget)}")

            trajectory.append({
                "event_idx": event_idx,
                "type": "correction",
                "entity_name": entity_name,
                "attr": attr,
                "old_val": old_val,
                "new_val": new_val,
                "content": content,
                "writes": stats.writes,
                "searches": stats.searches,
                "api_calls": stats.api_calls,
                "correction_applied": correction_ok,
                "turns": stats.turns,
            })
            if stats.error:
                print(f"  ERROR: {stats.error}")
                eval_error = stats.error
                break

        elif event_type == "question":
            # Adaptive comprehension: replace if required entities not stored
            if world is not None and template is not None:
                stored_contents = [e["content"] for e in backend.list()]
                event = template.maybe_replace_comprehension(
                    event, world, stored_contents,
                    rng_seed=seed + event_idx,
                )

            competency = event["competency"]
            question_text = event["question"]

            if quiet:
                print(f"  {event_label} QUESTION [{competency:12s}] ...",
                      end="", flush=True)
            else:
                print(f"  {event_label} QUESTION [{competency}] "
                      f"{question_text[:70]}")

            content = (
                f"=== Event {event_idx+1}/{total_events} [QUESTION] ===\n\n"
                f"**Question:**\n{question_text}\n\n"
                "Search your memory and call submit_answer(answer=\"...\")."
            )
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(
                client, model, messages, backend, budget)
            total_api_calls += stats.api_calls

            if stats.error:
                # Eval model unreachable — record as error, skip scoring
                print(f"           ERROR: {stats.error[:80]}")
                results.append(AgentResult(
                    question=question_text,
                    answer="",
                    ground_truth=str(event["answer"]),
                    competency=competency,
                    purpose=event.get("purpose", ""),
                    correct=False,
                    n_writes=stats.writes,
                    n_searches=stats.searches,
                    required_entities=event.get("required_entities", []),
                    api_calls=stats.api_calls,
                    elapsed=stats.elapsed,
                    retries=stats.retries,
                    error=stats.error,
                ))
                eval_error = stats.error
                break

            agent_answer = stats.answer or ""
            gt = str(event["answer"])

            # Rule-based check first (instant, no API call).
            # If rule passes, accept immediately. If rule fails,
            # defer judge call to run in parallel after all events.
            is_correct, reason = validate_with_fallback(
                agent_answer, gt, competency,
                question=question_text,
                judge_fn=None,  # no judge yet — deferred
            )

            result_idx = len(results)
            if not is_correct and competency != "abstention":
                # Needs judge — defer to post-loop parallel batch
                pending_judge.append((
                    result_idx,
                    question_text, gt, agent_answer,
                    competency,
                ))

            mark = "+" if is_correct else "?"  # "?" = pending judge
            via = reason.split(":")[0]

            if quiet:
                print(f" {mark} {stats.api_calls} calls "
                      f"{stats.elapsed:.1f}s via={via} "
                      f"budget={budget.remaining()}")
            else:
                search_qs = _extract_search_queries(stats.turns)
                search_info = (f"  searched: {', '.join(search_qs[:3])}"
                               if search_qs else "")
                print(f"           [{mark}] GT={gt[:50]}  "
                      f"A={agent_answer[:50]}")
                print(f"           {stats.api_calls} calls, "
                      f"{stats.elapsed:.1f}s, via={via}"
                      f"{search_info}")

            results.append(AgentResult(
                question=question_text,
                answer=agent_answer,
                ground_truth=gt,
                competency=competency,
                purpose=event.get("purpose", ""),
                correct=is_correct,
                n_writes=stats.writes,
                n_searches=stats.searches,
                required_entities=event.get("required_entities", []),
                validation_method=via,
                validation_reason=reason,
                api_calls=stats.api_calls,
                elapsed=stats.elapsed,
                retries=stats.retries,
            ))
            trajectory.append({
                "event_idx": event_idx,
                "type": "question",
                "competency": competency,
                "purpose": event.get("purpose", ""),
                "question": question_text,
                "ground_truth": gt,
                "agent_answer": agent_answer,
                "correct": is_correct,
                "content": content,
                "writes": stats.writes,
                "searches": stats.searches,
                "api_calls": stats.api_calls,
                "elapsed": round(stats.elapsed, 2),
                "turns": stats.turns,
            })

        elif event_type == "noise":
            # Noise documents: agent sees them but no action required.
            # Tests ability to filter irrelevant information.
            noise_text = event["document"]
            if not quiet:
                print(f"  {event_label} NOISE   {noise_text[:60]}...")
            content = (
                f"=== Event {event_idx+1}/{total_events} [INFO] ===\n\n"
                f"{noise_text}\n\n"
                "This is supplementary information. "
                "Store only if relevant to your tasks."
            )
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(client, model, messages, backend, budget)
            total_api_calls += stats.api_calls

        # Selective redaction: keep system prompt + memory state summary.
        # Without this, the model enters each event with zero context
        # about what it stored, causing widespread empty answers.
        # In no_redaction mode (long-context), keep full history.
        if not no_redaction:
            del messages[1:]  # Remove everything after system prompt
            stored_entries = backend.list()
            if stored_entries:
                stored_names = [e["content"].split("|")[0].strip()
                                for e in stored_entries]
                mem_summary = (
                    f"[{event_idx+1}/{total_events} done]\n\n"
                    f"Your memory contains {len(stored_entries)} entries: "
                    + ", ".join(stored_names[:30])
                    + (f" ... (+{len(stored_names)-30} more)"
                       if len(stored_names) > 30 else "")
                    + f"\nBudget: {budget.remaining()} writes remaining."
                )
            else:
                mem_summary = (
                    f"[{event_idx+1}/{total_events} done]\n"
                    f"Your memory is empty. Budget: {budget.remaining()} "
                    f"writes remaining."
                )
            messages.append({"role": "user", "content": mem_summary})
            messages.append({"role": "assistant", "content": "OK."})

    # Parallel judge validation for rule-failed answers.
    # This runs all pending judge calls concurrently instead of
    # blocking after each question — typically 3-5x faster.
    if pending_judge:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _run_judge(item):
            idx, question, gt_, answer, competency = item
            try:
                ok, reason = llm_judge_validate_sync(
                    judge_client, question, gt_, answer, competency)
                return idx, ok, f"judge:{reason}"
            except Exception as exc:
                return idx, False, f"judge:failed({exc})"

        judge_t0 = time.time()
        n_pending = len(pending_judge)
        print(f"  Judging {n_pending} answers in parallel ...", end="",
              flush=True)
        with ThreadPoolExecutor(max_workers=min(n_pending, 4)) as pool:
            futures = [pool.submit(_run_judge, item)
                       for item in pending_judge]
            for future in as_completed(futures):
                idx, ok, reason = future.result()
                results[idx] = AgentResult(
                    question=results[idx].question,
                    answer=results[idx].answer,
                    ground_truth=results[idx].ground_truth,
                    competency=results[idx].competency,
                    purpose=results[idx].purpose,
                    correct=ok,
                    n_writes=results[idx].n_writes,
                    n_searches=results[idx].n_searches,
                    required_entities=results[idx].required_entities,
                    validation_method=reason.split(":")[0],
                    validation_reason=reason,
                    api_calls=results[idx].api_calls,
                    elapsed=results[idx].elapsed,
                    retries=results[idx].retries,
                )
        judge_elapsed = time.time() - judge_t0
        judge_results = sum(1 for i, _, _, _, _ in pending_judge
                           if results[i].correct)
        print(f" {judge_results}/{n_pending} correct, {judge_elapsed:.1f}s")

        # Update trajectory entries with post-judging correct values
        judged_indices = {i for i, _, _, _, _ in pending_judge}
        result_idx_counter = 0
        for t_entry in trajectory:
            if t_entry.get("type") == "question":
                if result_idx_counter in judged_indices:
                    t_entry["correct"] = results[result_idx_counter].correct
                result_idx_counter += 1

    total_elapsed = time.time() - run_t0
    correct_count = sum(r.correct for r in results)
    total_q = len(results)
    pct = f"{correct_count/total_q:.0%}" if total_q else "n/a"

    if quiet:
        summary = (f"  --- Summary: {correct_count}/{total_q} correct "
                   f"({pct}) | "
                   f"{total_api_calls} API calls | "
                   f"{budget.writes_used} writes | "
                   f"{total_elapsed:.1f}s total")
        if eval_error:
            summary += f" | ERROR: {eval_error[:80]}"
        print(summary + " ---")
    else:
        print(f"\n  {'═' * 50}")
        print(f"  RESULTS")
        print(f"  {'═' * 50}")
        print(f"  Score: {correct_count}/{total_q} ({pct})")
        print(f"  {_budget_bar(budget.writes_used, write_budget)}")
        stored_entries = backend.list()
        print(f"  Memory: {len(stored_entries)} entries stored")
        print(f"  API calls: {total_api_calls}  "
              f"Time: {total_elapsed:.1f}s")

        # Per-competency breakdown
        from collections import defaultdict as _defaultdict
        comp_stats: dict[str, list[bool]] = _defaultdict(list)
        for r in results:
            comp_stats[r.competency].append(r.correct)
        if comp_stats:
            print(f"\n  Per-competency:")
            for comp, vals in sorted(comp_stats.items()):
                ok = sum(vals)
                print(f"    {comp:20s} {ok}/{len(vals)} "
                      f"({ok/len(vals):.0%})")

        # Correction summary
        if correction_results:
            ok = sum(1 for c in correction_results if c["success"])
            print(f"\n  Corrections: {ok}/{len(correction_results)} "
                  f"successfully updated")
            for c in correction_results:
                mark = "OK" if c["success"] else "MISS"
                print(f"    [{mark}] {c['entity']}.{c['attr']}: "
                      f"{c['chain']}")

        # Timing distribution
        if results:
            times = [r.elapsed for r in results if r.elapsed > 0]
            if times:
                avg_t = sum(times) / len(times)
                max_t = max(times)
                print(f"\n  Timing: avg={avg_t:.1f}s  "
                      f"max={max_t:.1f}s  total={total_elapsed:.1f}s")

        if eval_error:
            print(f"\n  ERROR: {eval_error[:120]}")
        print(f"  {'═' * 50}")

    stored_contents = [e["content"] for e in backend.list()]
    if hasattr(backend, "close"):
        backend.close()
    return results, budget.writes_used, stored_contents, eval_error, trajectory
