"""Inspect AI solver for MemoryBench: sequential 25-task streaming evaluation."""

from __future__ import annotations

import re
from typing import Any

from inspect_ai.model import ChatMessageAssistant, ChatMessageUser
from inspect_ai.solver import Generate, Solver, TaskState, solver

SYSTEM_PROMPT = """You are participating in a streaming memory evaluation.

You will receive a sequence of {n_tasks} tasks. Each task contains:
1. Documents with information to read and potentially store
2. A question to answer based on your stored memories

You have access to memory tools:
- memory_write(content): Store information (costs 1 write, budget: {budget})
- memory_search(query, top_k): Search stored memories (free)
- memory_update(memory_id, content): Update existing memory (costs 1 write)
- memory_delete(memory_id): Remove a memory (free, no budget refund)
- memory_list(): List all memories (free)

IMPORTANT:
- Your write budget is LIMITED to {budget} writes total across ALL tasks.
- Choose carefully what to store. Not everything is worth saving.
- When answering, ALWAYS call submit_answer(answer="your answer").
- If you cannot answer a question from your memories, call submit_answer(answer="I don't have enough information").
- Read all documents carefully before deciding what to store.
"""

TASK_TEMPLATE = """=== Task {task_num}/{total} ===

**Documents:**
{documents}

**Question:**
{question}

Instructions:
1. Read the documents above and decide what to store in memory.
2. Search your memory for information relevant to the question.
3. Call submit_answer(answer="...") with your final answer.
"""


def _format_documents(docs: list[str]) -> str:
    """Format document list for presentation."""
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[Document {i}]\n{doc}")
    return "\n\n".join(parts)


def _count_tool_calls(messages: list, start_idx: int = 0) -> tuple[int, int]:
    """Count memory write and search calls in messages from start_idx."""
    n_writes = 0
    n_searches = 0
    for msg in messages[start_idx:]:
        if hasattr(msg, "content") and isinstance(msg.content, list):
            for part in msg.content:
                fn = getattr(part, "function", None)
                if fn in ("memory_write", "memory_update"):
                    n_writes += 1
                elif fn in ("memory_search", "memory_list"):
                    n_searches += 1
    return n_writes, n_searches


def _extract_answer(messages: list) -> str | None:
    """Extract the submitted answer from message history."""
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            match = re.search(r"ANSWER_SUBMITTED:\s*(.+)", msg.content)
            if match:
                return match.group(1).strip()
        # Check tool results
        if hasattr(msg, "content") and isinstance(msg.content, list):
            for part in msg.content:
                if hasattr(part, "text"):
                    match = re.search(
                        r"ANSWER_SUBMITTED:\s*(.+)", part.text)
                    if match:
                        return match.group(1).strip()
    return None


@solver
def memorybench_solver(
    n_tasks: int = 25,
    budget: int = 30,
    mem_budget: Any = None,
) -> Solver:
    """Solver that processes tasks sequentially in a streaming fashion.

    Each task:
    1. Presents documents + question as a user message
    2. Agent uses memory tools and calls submit_answer()
    3. Answer is stored in state.store for the scorer

    Args:
        n_tasks: Number of tasks to process.
        budget: Write budget (for display only).
        mem_budget: MemoryBudget instance (for tracking writes_used).
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        tasks = state.metadata.get("benchmark_tasks", [])
        n = min(n_tasks, len(tasks))

        answers: list[dict[str, Any]] = []

        for i, task_data in enumerate(tasks[:n]):
            # Skip tasks without questions (still present docs)
            question = task_data.get("question")
            if question is None:
                continue

            docs_text = _format_documents(task_data["documents"])
            msg_start_idx = len(state.messages)

            user_content = TASK_TEMPLATE.format(
                task_num=i + 1,
                total=n,
                documents=docs_text,
                question=question,
            )
            state.messages.append(ChatMessageUser(content=user_content))

            # Let agent use tools and answer
            state = await generate(state, tool_calls="loop")

            # Extract answer and count tool calls BEFORE redaction
            answer = _extract_answer(state.messages)
            n_writes, n_searches = _count_tool_calls(
                state.messages, msg_start_idx)

            # Nuclear redaction: delete ALL messages for this task
            # (user + assistant + tool) to prevent context-window bypass.
            # This defeats: tool-call notepad attacks, search result leaks,
            # and any scrollback through prior task data.
            del state.messages[msg_start_idx:]
            state.messages.append(ChatMessageUser(
                content=f"[Task {i + 1}/{n} completed. Documents redacted.]"
            ))
            state.messages.append(ChatMessageAssistant(
                content=f"Task {i + 1} of {n} completed."
            ))
            answers.append({
                "task_id": task_data["task_id"],
                "global_id": task_data.get("global_id"),
                "question": question,
                "answer": answer,
                "competency": task_data.get("competency"),
                "domain": task_data.get("domain"),
                "ground_truth": task_data.get("ground_truth"),
                "required_entities": task_data.get("required_entities", []),
                "n_writes": n_writes,
                "n_searches": n_searches,
                "searched_before_answering": n_searches > 0,
            })

        # Store results for scorer
        writes_used = mem_budget.writes_used if mem_budget else 0
        state.store.set("benchmark_answers", answers)
        state.store.set("writes_used", writes_used)
        state.completed = True
        return state

    return solve
