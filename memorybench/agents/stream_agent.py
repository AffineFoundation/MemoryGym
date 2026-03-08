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

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from memorybench.evaluation.llm_judge import llm_judge_validate_sync
from memorybench.evaluation.validators import validate_with_fallback
from memorybench.memory.backends.chromadb_backend import ChromaDBBackend
from memorybench.memory.budget import MemoryBudget

# Type alias: any backend implementing store/search/get/forget/list
MemoryBackend = Any

SYSTEM_PROMPT = """You are participating in a memory management evaluation.
Write budget: {budget} total writes. Be selective — you'll see more entities than you can store.

## Event Types
1. DOCUMENTS: Entity data to read and store selectively.
2. CORRECTIONS: Updated data. You MUST update stored memories.
3. QUESTIONS: Answer from stored memories only.

## Memory Tools

Call tools by outputting JSON blocks:

**memory_store** — Store info (costs 1 write, budget: {budget}):
<tool_call>{{"name": "memory_store", "arguments": {{"content": "info to store"}}}}</tool_call>

**memory_search** — Search stored memories (free, uses substring matching):
<tool_call>{{"name": "memory_search", "arguments": {{"query": "entity name"}}}}</tool_call>

**memory_forget** — Delete entry by ID (free):
<tool_call>{{"name": "memory_forget", "arguments": {{"memory_id": "id"}}}}</tool_call>

**memory_list** — List all memories (free):
<tool_call>{{"name": "memory_list", "arguments": {{}}}}</tool_call>

**submit_answer** — Submit your final answer:
<tool_call>{{"name": "submit_answer", "arguments": {{"answer": "your answer"}}}}</tool_call>

## Critical: Handling Corrections
When you receive a CORRECTION:
1. memory_search the entity name
2. memory_forget the old entry
3. memory_store the corrected data
This costs 1 write but ensures your answers reflect current data.
Failing to update = wrong answers on update questions.

## Storage Strategy
- Store data compactly: "EntityName | attr1: val1, attr2: val2, ..."
- Prioritize entities with extreme/distinctive values
- Skip unremarkable entities when budget is tight
- IMPORTANT: Reserve ~20% of your budget for corrections. \
Corrections will arrive later and each costs 1 write to update.

## Answering Questions
- Search by entity name, then submit_answer with the value
- For comparison/synthesis: answer as "EntityName (value)"
- If data not in memory: submit "I don't have enough information"
- Do NOT guess or fabricate values
- ALWAYS call submit_answer for every question
"""

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL,
)

# Valid tool names for bare-JSON detection
_KNOWN_TOOLS = {
    "memory_store", "memory_search", "memory_get",
    "memory_forget", "memory_list", "submit_answer",
}

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


def _format_documents(docs: list[str]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[Document {i}]\n{doc}")
    return "\n\n".join(parts)


def _execute_tool(
    name: str, args: dict, backend: MemoryBackend, budget: MemoryBudget,
) -> tuple[str, str | None]:
    """Execute a tool call. Returns (result_text, submitted_answer_or_None)."""
    if name == "submit_answer":
        return f"ANSWER_SUBMITTED: {args.get('answer', '')}", args.get("answer", "")

    if name == "memory_store":
        content = args.get("content", "")
        if len(content) > 2000:
            return "Content exceeds 2000 character limit.", None
        if not budget.can_write():
            return f"Budget exhausted ({budget.writes_used}/{budget.total_writes}).", None
        memory_id = args.get("memory_id")
        if memory_id:
            existing = backend.get(memory_id)
            if not existing:
                return "Entry not found.", None
        budget.consume_write()
        entry_id = backend.store(content, memory_id=memory_id)
        return f"Stored (id={entry_id}). {budget.remaining()} writes left.", None

    if name == "memory_search":
        results = backend.search(args.get("query", ""), args.get("top_k", 5))
        if not results:
            return "No results found.", None
        lines = [f"[{r['id']}] {r['content']}" for r in results]
        return "\n".join(lines), None

    if name == "memory_get":
        entry = backend.get(args.get("memory_id", ""))
        if not entry:
            return "Entry not found.", None
        return f"[{entry['id']}] {entry['content']}", None

    if name == "memory_forget":
        ok = backend.forget(args.get("memory_id", ""))
        return ("Deleted." if ok else "Entry not found."), None

    if name == "memory_list":
        entries = backend.list()
        if not entries:
            return "Memory is empty.", None
        lines = [f"[{e['id']}] {e['content']}" for e in entries]
        return "\n".join(lines), None

    return f"Unknown tool: {name}", None


def _extract_tool_calls(text: str) -> list[dict]:
    """Extract tool calls from text — supports <tool_call> XML and bare JSON."""
    calls = []
    # 1) Try XML-wrapped format first
    for match in _TOOL_CALL_RE.finditer(text):
        try:
            call = json.loads(match.group(1))
            if call.get("name") in _KNOWN_TOOLS:
                calls.append(call)
        except json.JSONDecodeError:
            continue
    if calls:
        return calls
    # 2) Fallback: bare JSON (Qwen-style)
    for match in _BARE_JSON_RE.finditer(text):
        try:
            call = json.loads(match.group(0))
            if call.get("name") in _KNOWN_TOOLS:
                calls.append(call)
        except json.JSONDecodeError:
            continue
    return calls


def _parse_and_execute(
    text: str, backend: MemoryBackend, budget: MemoryBudget,
) -> tuple[list[str], str | None, int, int]:
    """Parse tool_call blocks and execute. Returns (results, answer, writes, searches)."""
    results = []
    answer = None
    n_writes = n_searches = 0

    for call in _extract_tool_calls(text):
        name = call.get("name", "")
        args = call.get("arguments", {})

        if name == "memory_store":
            n_writes += 1
        elif name in ("memory_search", "memory_list", "memory_get"):
            n_searches += 1

        result_text, submitted = _execute_tool(name, args, backend, budget)
        results.append(f"[{name}] {result_text}")

        if submitted is not None:
            answer = submitted

    return results, answer, n_writes, n_searches


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


def _run_tool_loop(
    client: OpenAI, model: str, messages: list[dict],
    backend: MemoryBackend, budget: MemoryBudget,
    max_turns: int = 10, max_retries: int = 10,
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

        results, answer, n_w, n_s = _parse_and_execute(text, backend, budget)
        stats.writes += n_w
        stats.searches += n_s

        if answer is not None:
            stats.answer = answer
            break

        if not results:
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
    backend: MemoryBackend | None = None,
    world: Any = None,
    template: Any = None,
    seed: int = 0,
) -> tuple[list[AgentResult], int, list[dict], str | None]:
    """Run a real LLM agent on a WorldTemplate event stream.

    Args:
        model: Model name (OpenAI-compatible).
        stream: List of events from WorldTemplate.generate_stream().
        write_budget: Total memory writes allowed.
        api_base: API base URL (default: OpenAI).
        api_key: API key (default: from env).
        verbose: Print per-event details.
        backend: Memory backend (default: ChromaDBBackend). Pass a Mem0Backend
            for mem0-based memory.
        world: World instance for adaptive comprehension questions.
        template: WorldTemplate instance for adaptive comprehension questions.
        seed: Random seed for replacement question generation.

    Returns:
        (results, writes_used, stored_contents, error_or_none)
    """
    if api_key is None:
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CHUTES_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set OPENAI_API_KEY or CHUTES_API_KEY environment variable")

    kwargs: dict[str, Any] = {"api_key": api_key}
    if api_base:
        kwargs["base_url"] = api_base

    client = OpenAI(**kwargs)

    # Judge client: always uses Chutes API for cheap multi-model judging
    judge_api_key = os.environ.get("CHUTES_API_KEY") or api_key
    judge_client = OpenAI(
        api_key=judge_api_key,
        base_url="https://llm.chutes.ai/v1",
    )

    if backend is None:
        backend = ChromaDBBackend()
    budget = MemoryBudget(total_writes=write_budget)

    total_events = len(stream)
    eval_error: str | None = None
    messages: list[dict] = [{
        "role": "system",
        "content": SYSTEM_PROMPT.format(budget=write_budget),
    }]

    results: list[AgentResult] = []
    pending_judge: list[tuple] = []  # (result_idx, question, gt, answer, competency)
    total_api_calls = 0
    run_t0 = time.time()

    for event_idx, event in enumerate(stream):
        msg_start = len(messages)
        event_type = event["type"]
        event_label = f"[{event_idx+1}/{total_events}]"

        if event_type == "ingest":
            n_ents = len(event.get("entity_names", []))
            print(f"  {event_label} INGEST  {n_ents} entities ...",
                  end="", flush=True)

            docs_text = _format_documents(event["documents"])
            content = (
                f"=== Event {event_idx+1}/{total_events} [DOCUMENTS] ===\n\n"
                f"**Documents:**\n{docs_text}\n\n"
                "No question. Store important entity data."
            )
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(client, model, messages, backend, budget)
            total_api_calls += stats.api_calls

            print(f" {stats.api_calls} calls {stats.elapsed:.1f}s "
                  f"budget={budget.remaining()}")
            if stats.error:
                print(f"  ERROR: {stats.error}")
                eval_error = stats.error
                break

        elif event_type == "correction":
            entity_attr = f"{event['entity_name']}.{event['attr']}"
            print(f"  {event_label} CORRECT {entity_attr} ...",
                  end="", flush=True)

            content = (
                f"=== Event {event_idx+1}/{total_events} [CORRECTION] ===\n\n"
                f"**Correction Notice:**\n{event['notice']}\n\n"
                "Update your stored memories with the corrected value."
            )
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(client, model, messages, backend, budget)
            total_api_calls += stats.api_calls

            print(f" {stats.api_calls} calls {stats.elapsed:.1f}s "
                  f"budget={budget.remaining()}")
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
            print(f"  {event_label} QUESTION [{event['competency']:12s}] ...",
                  end="", flush=True)

            content = (
                f"=== Event {event_idx+1}/{total_events} [QUESTION] ===\n\n"
                f"**Question:**\n{event['question']}\n\n"
                "Search your memory and call submit_answer(answer=\"...\")."
            )
            messages.append({"role": "user", "content": content})
            stats = _run_tool_loop(
                client, model, messages, backend, budget)
            total_api_calls += stats.api_calls

            if stats.error:
                # Eval model unreachable — record as error, skip scoring
                print(f" ERROR {stats.error[:80]}")
                results.append(AgentResult(
                    question=event["question"],
                    answer="",
                    ground_truth=str(event["answer"]),
                    competency=event["competency"],
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
                agent_answer, gt, event["competency"],
                question=event["question"],
                judge_fn=None,  # no judge yet — deferred
            )

            result_idx = len(results)
            if not is_correct and event["competency"] != "abstention":
                # Needs judge — defer to post-loop parallel batch
                pending_judge.append((
                    result_idx,
                    event["question"], gt, agent_answer,
                    event["competency"],
                ))

            mark = "+" if is_correct else "?"  # "?" = pending judge
            via = reason.split(":")[0]
            print(f" {mark} {stats.api_calls} calls {stats.elapsed:.1f}s "
                  f"via={via} "
                  f"budget={budget.remaining()}")

            if verbose:
                print(f"           A={agent_answer[:60]}")
                print(f"          GT={gt[:60]}")
                if reason:
                    print(f"       Valid: {reason}")

            results.append(AgentResult(
                question=event["question"],
                answer=agent_answer,
                ground_truth=gt,
                competency=event["competency"],
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

        # Selective redaction: keep system prompt + memory state summary.
        # Without this, the model enters each event with zero context
        # about what it stored, causing widespread empty answers.
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

    total_elapsed = time.time() - run_t0
    correct_count = sum(r.correct for r in results)
    total_q = len(results)
    pct = f"{correct_count/total_q:.0%}" if total_q else "n/a"
    summary = (f"  --- Summary: {correct_count}/{total_q} correct "
               f"({pct}) | "
               f"{total_api_calls} API calls | "
               f"{budget.writes_used} writes | "
               f"{total_elapsed:.1f}s total")
    if eval_error:
        summary += f" | ERROR: {eval_error[:80]}"
    print(summary + " ---")

    stored_contents = [e["content"] for e in backend.list()]
    return results, budget.writes_used, stored_contents, eval_error
