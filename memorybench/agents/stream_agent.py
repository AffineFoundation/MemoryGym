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

You will receive a stream of events in unpredictable order:

1. **DOCUMENTS**: Entity data. Read and store what seems important.
2. **CORRECTIONS**: Data correction notices. Update your stored memories.
3. **QUESTIONS**: Answer from your stored memories.

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

## Strategy

- Store entity data compactly: "EntityName | attr1: val1, attr2: val2, ..."
- When corrections arrive, search for the entity, delete old entry, store corrected data.
- For questions, search by entity name, then submit_answer.
- For comparison questions, answer as "EntityName (value)".
- If data is not in memory, submit "I don't have enough information".
- Write budget: {budget} total. Be selective.
- ALWAYS call submit_answer when there is a question.
"""

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL,
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


def _parse_and_execute(
    text: str, backend: MemoryBackend, budget: MemoryBudget,
) -> tuple[list[str], str | None, int, int]:
    """Parse tool_call blocks and execute. Returns (results, answer, writes, searches)."""
    results = []
    answer = None
    n_writes = n_searches = 0

    for match in _TOOL_CALL_RE.finditer(text):
        try:
            call = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

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


def _run_tool_loop(
    client: OpenAI, model: str, messages: list[dict],
    backend: MemoryBackend, budget: MemoryBudget,
    max_turns: int = 10,
) -> _LoopStats:
    """Run text-based tool loop until submit_answer or max_turns."""
    stats = _LoopStats()
    t0 = time.time()

    for turn in range(max_turns):
        response = client.chat.completions.create(
            model=model, messages=messages,
        )
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
) -> tuple[list[AgentResult], int, list[dict]]:
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
        (results, writes_used, stored_contents)
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
    messages: list[dict] = [{
        "role": "system",
        "content": SYSTEM_PROMPT.format(budget=write_budget),
    }]

    results: list[AgentResult] = []
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

            agent_answer = stats.answer or ""
            gt = str(event["answer"])

            def _judge_fn(q, gt_, ans, comp):
                return llm_judge_validate_sync(
                    judge_client, q, gt_, ans, comp)

            judge_t0 = time.time()
            is_correct, reason = validate_with_fallback(
                agent_answer, gt, event["competency"],
                question=event["question"],
                judge_fn=_judge_fn,
            )
            judge_elapsed = time.time() - judge_t0

            mark = "+" if is_correct else "-"
            via = reason.split(":")[0]  # "rule" or "judge"
            print(f" {mark} {stats.api_calls} calls {stats.elapsed:.1f}s "
                  f"via={via} {judge_elapsed:.1f}s "
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
            ))

        # Nuclear redaction: keep only system prompt + 1 placeholder pair
        del messages[1:]  # Remove everything after system prompt
        messages.append({
            "role": "user",
            "content": f"[{event_idx+1}/{total_events} done]",
        })
        messages.append({"role": "assistant", "content": "OK."})

    total_elapsed = time.time() - run_t0
    correct_count = sum(r.correct for r in results)
    total_q = len(results)
    print(f"  --- Summary: {correct_count}/{total_q} correct "
          f"({correct_count/total_q:.0%}) | "
          f"{total_api_calls} API calls | "
          f"{budget.writes_used} writes | "
          f"{total_elapsed:.1f}s total ---")

    stored_contents = [e["content"] for e in backend.list()]
    return results, budget.writes_used, stored_contents
