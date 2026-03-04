"""LLM agent for MemoryBench: text-based tool calling via Chutes API."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from memorybench.domains.base import Task, TaskResult
from memorybench.evaluation.validators import AnswerValidator
from memorybench.memory.backends.mock_backend import MockBackend
from memorybench.memory.budget import MemoryBudget
from memorybench.simulation.agents import TaskTrace

_VALIDATOR = AnswerValidator()

CHUTES_BASE_URL = "https://llm.chutes.ai/v1/"

SYSTEM_PROMPT = """You are participating in a streaming memory evaluation.

You will receive {n_tasks} tasks over time. Each task gives you documents about entities (people, products, researchers, etc.) and asks a question. Future tasks will ask about entities you saw in earlier tasks, so you MUST store entity data for later recall.

## Memory Tools

Call tools by outputting JSON blocks. You may call multiple tools per response.

**memory_write** — Store info (costs 1 write, budget: {budget}):
<tool_call>{{"name": "memory_write", "arguments": {{"content": "info to store"}}}}</tool_call>

**memory_search** — Search stored memories. IMPORTANT: search uses substring matching, so use short queries like entity names (free):
<tool_call>{{"name": "memory_search", "arguments": {{"query": "entity name"}}}}</tool_call>

**memory_update** — Update entry by ID (costs 1 write):
<tool_call>{{"name": "memory_update", "arguments": {{"memory_id": "id", "content": "new content"}}}}</tool_call>

**memory_delete** — Delete entry by ID (free):
<tool_call>{{"name": "memory_delete", "arguments": {{"memory_id": "id"}}}}</tool_call>

**memory_list** — List all memories (free):
<tool_call>{{"name": "memory_list", "arguments": {{}}}}</tool_call>

**submit_answer** — Submit your final answer:
<tool_call>{{"name": "submit_answer", "arguments": {{"answer": "your answer"}}}}</tool_call>

## Strategy

1. **Store only entity data** — one write per entity with ALL its numeric attributes. Skip noise (shipment notices, planning updates, seminar announcements, workshop info). Format: "EntityName | attr1: val1, attr2: val2, ..."
2. **Search by entity name** before answering. Search uses substring matching, so query "Dr. Alice Smith" or just "Alice Smith" — NOT long phrases like "Alice Smith's citation count".
3. **Comparison questions**: Search EACH entity mentioned in the question separately, gather their values, then compare and answer in the format "EntityName (value)". Example: "Dr. Alice Smith (3000)"
4. **Correction notices**: When a document says "CORRECTION: X's value changed from A to B", immediately search for X, delete the old entry, and write a new entry with the corrected value.
5. **Answering**: After searching, read the stored content carefully and extract the exact number asked for. If the attribute is genuinely not in the stored entry, submit "I don't have enough information".
6. ALWAYS call submit_answer. For comparison questions, answer with "EntityName (value)".

## Rules
- Write budget: {budget} total across ALL tasks. Be efficient — skip noise, store only entities.
- ALWAYS call submit_answer to answer.
"""

TASK_TEMPLATE = """=== Task {task_num}/{total} ===

**Documents:**
{documents}

**Question:**
{question}

Steps: 1) Store any new entities from the documents. 2) Search memory for each entity in the question. 3) Submit your answer."""

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL,
)


def _format_documents(docs: list[str]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[Document {i}]\n{doc}")
    return "\n\n".join(parts)


def _execute_tool(
    name: str, args: dict, backend: MockBackend, budget: MemoryBudget,
) -> tuple[str, str | None]:
    """Execute a tool call. Returns (result_text, submitted_answer_or_None)."""
    if name == "submit_answer":
        return f"ANSWER_SUBMITTED: {args.get('answer', '')}", args.get("answer", "")

    if name == "memory_write":
        if not budget.can_write():
            return f"Budget exhausted ({budget.writes_used}/{budget.total_writes}).", None
        budget.consume_write()
        entry_id = backend.add(args.get("content", ""))
        return f"Stored (id={entry_id}). {budget.remaining()} writes left.", None

    if name == "memory_search":
        results = backend.search(args.get("query", ""), args.get("top_k", 5))
        if not results:
            return "No results found.", None
        lines = [f"[{r['id']}] {r['content'][:200]}" for r in results]
        return "\n".join(lines), None

    if name == "memory_update":
        if not budget.can_write():
            return "Budget exhausted.", None
        ok = backend.update(args.get("memory_id", ""), args.get("content", ""))
        if not ok:
            return "Entry not found.", None
        budget.consume_write()
        return f"Updated. {budget.remaining()} writes left.", None

    if name == "memory_delete":
        ok = backend.delete(args.get("memory_id", ""))
        return ("Deleted." if ok else "Entry not found."), None

    if name == "memory_list":
        entries = backend.list_all()
        if not entries:
            return "Memory is empty.", None
        lines = [f"[{e['id']}] {e['content'][:200]}" for e in entries]
        return "\n".join(lines), None

    return f"Unknown tool: {name}", None


def _parse_and_execute(
    text: str, backend: MockBackend, budget: MemoryBudget,
) -> tuple[list[str], str | None, int, int]:
    """Parse tool_call blocks from model output and execute them.

    Returns (result_lines, submitted_answer, n_writes, n_searches).
    """
    results = []
    answer = None
    n_writes = 0
    n_searches = 0

    for match in _TOOL_CALL_RE.finditer(text):
        try:
            call = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        name = call.get("name", "")
        args = call.get("arguments", {})

        if name in ("memory_write", "memory_update"):
            n_writes += 1
        elif name in ("memory_search", "memory_list"):
            n_searches += 1

        result_text, submitted = _execute_tool(name, args, backend, budget)
        results.append(f"[{name}] {result_text}")

        if submitted is not None:
            answer = submitted

    return results, answer, n_writes, n_searches


def _run_tool_loop(
    client: OpenAI,
    model: str,
    messages: list[dict],
    backend: MockBackend,
    budget: MemoryBudget,
    max_turns: int = 10,
) -> tuple[str | None, int, int]:
    """Run text-based tool loop until submit_answer or max_turns.

    Returns (answer, total_writes, total_searches).
    """
    total_writes = 0
    total_searches = 0

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        text = response.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": text})

        # Parse tool calls from text
        results, answer, n_w, n_s = _parse_and_execute(text, backend, budget)
        total_writes += n_w
        total_searches += n_s

        if answer is not None:
            return answer, total_writes, total_searches

        if not results:
            # No tool calls and no answer — model may have answered in plain text
            break

        # Feed tool results back
        messages.append({"role": "user", "content": "Tool results:\n" + "\n".join(results)})

    return None, total_writes, total_searches


def run_llm_agent(
    model: str,
    tasks: list[Task],
    seed: int,
    write_budget: int = 50,
    verbose: bool = False,
) -> tuple[list[TaskResult], int, list[TaskTrace]]:
    """Run a real LLM agent on the task stream via Chutes API.

    Returns the same (results, writes_used, traces) as simulate_agent().
    """
    api_key = os.environ.get("CHUTES_API_KEY")
    if not api_key:
        raise RuntimeError("CHUTES_API_KEY environment variable is required")

    client = OpenAI(base_url=CHUTES_BASE_URL, api_key=api_key)
    backend = MockBackend()
    budget = MemoryBudget(total_writes=write_budget)

    n_tasks = sum(1 for t in tasks if t.question is not None)
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(
            n_tasks=n_tasks, budget=write_budget,
        )},
    ]

    results: list[TaskResult] = []
    traces: list[TaskTrace] = []

    for i, task in enumerate(tasks):
        trace = TaskTrace(
            task_id=task.task_id,
            domain=task.domain,
            budget_before=budget.remaining(),
            n_docs_received=len(task.documents),
            n_new_entities=len(task.new_entity_names),
        )

        if task.question is None:
            traces.append(trace)
            continue

        msg_start = len(messages)
        docs_text = _format_documents(task.documents)
        user_content = TASK_TEMPLATE.format(
            task_num=i + 1, total=len(tasks),
            documents=docs_text,
            question=task.question.question,
        )
        messages.append({"role": "user", "content": user_content})

        answer, n_writes, n_searches = _run_tool_loop(
            client, model, messages, backend, budget,
        )

        # Redact this task's messages (prevent context leakage)
        del messages[msg_start:]
        messages.append({"role": "user", "content": f"[Task {i+1}/{len(tasks)} completed.]"})
        messages.append({"role": "assistant", "content": "Understood."})

        trace.budget_after = budget.remaining()
        trace.searched_before_answering = n_searches > 0
        trace.n_search_hits = n_searches
        trace.stored_any = n_writes > 0

        agent_answer = answer or ""
        gt = task.question.answer
        is_correct = _VALIDATOR.validate(str(agent_answer), gt, task.question.competency)

        results.append(TaskResult(
            task_id=task.task_id,
            competency=task.question.competency,
            domain=task.domain,
            is_correct=is_correct,
            agent_answer=agent_answer,
            expected_answer=gt,
            question_text=task.question.question,
            failure_reason="" if is_correct else "incorrect",
            search_hits=n_searches,
        ))
        traces.append(trace)

        if verbose:
            status = "✓" if is_correct else "✗"
            print(f"  T{task.task_id:02d} [{task.domain}] {status}  "
                  f"writes={n_writes} searches={n_searches} "
                  f"budget={budget.remaining()}")
            if not is_correct:
                print(f"       A: {agent_answer} ≠ {gt}")

    return results, budget.writes_used, traces
