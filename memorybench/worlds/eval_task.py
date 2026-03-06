"""Inspect AI task for WorldTemplate-based memory evaluation.

Usage:
    # Run with specific seed and template:
    inspect eval memorybench/worlds/eval_task.py -M openai/gpt-4o \
        -T seed=42 -T template=company

    # Run with mem0 backend:
    inspect eval memorybench/worlds/eval_task.py -M openai/gpt-4o \
        -T seed=42 -T backend=mem0
"""

from __future__ import annotations

import hashlib
import re
from random import Random
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser
from inspect_ai.solver import Generate, Solver, TaskState, chain, solver, use_tools

from memorybench.inspect_task.tools import create_memory_tools, submit_answer
from memorybench.worlds import ALL_TEMPLATES
from memorybench.worlds.base import Correction, GeneratedQA, World, WorldTemplate

_TEMPLATES = ALL_TEMPLATES

SYSTEM_PROMPT = """You are participating in a memory management evaluation.

You will receive a stream of events. Events can be:

1. **DOCUMENTS**: Entity data to read and store. You don't know what questions come later.
2. **CORRECTIONS**: Data correction notices. Update your stored memories.
3. **QUESTIONS**: Answer from memory. Search and call submit_answer().

Events arrive in unpredictable order — questions may appear between document batches.

You have access to memory tools:
- memory_store(content, memory_id?): Store or update a memory (costs 1 write, \
budget: {budget})
- memory_search(query, top_k): Search stored memories (free)
- memory_get(memory_id): Retrieve a single memory by ID (free)
- memory_forget(memory_id): Remove a memory (free, no budget refund)
- memory_list(): List all memories (free)

IMPORTANT:
- Your write budget is LIMITED to {budget} writes total.
- Store entity data proactively — you won't know what questions come later.
- When corrections arrive, update relevant memories.
- When answering, ALWAYS call submit_answer(answer="your answer").
- If you cannot answer from memory, call submit_answer(answer="I don't have \
enough information").
"""

INGEST_TEMPLATE = """=== Event {event_num}/{total_events} [DOCUMENTS] ===

**Documents:**
{documents}

No question. Read and store important entity data for future recall."""

CORRECTION_TEMPLATE = """=== Event {event_num}/{total_events} [CORRECTION] ===

**Correction Notice:**
{notice}

Update your stored memories with the corrected value."""

QUESTION_TEMPLATE = """=== Event {event_num}/{total_events} [QUESTION] ===

**Question:**
{question}

Search your memory and call submit_answer(answer="...") with your final answer."""


def _format_documents(docs: list[str]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[Document {i}]\n{doc}")
    return "\n\n".join(parts)


def _extract_answer(messages: list) -> str | None:
    for msg in reversed(messages):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            match = re.search(r"ANSWER_SUBMITTED:\s*(.+)", msg.content)
            if match:
                return match.group(1).strip()
        if hasattr(msg, "content") and isinstance(msg.content, list):
            for part in msg.content:
                if hasattr(part, "text"):
                    match = re.search(
                        r"ANSWER_SUBMITTED:\s*(.+)", part.text)
                    if match:
                        return match.group(1).strip()
    return None


def _count_tool_calls(messages: list, start_idx: int = 0) -> tuple[int, int]:
    n_writes = n_searches = 0
    for msg in messages[start_idx:]:
        if hasattr(msg, "content") and isinstance(msg.content, list):
            for part in msg.content:
                fn = getattr(part, "function", None)
                if fn == "memory_store":
                    n_writes += 1
                elif fn in ("memory_search", "memory_list", "memory_get"):
                    n_searches += 1
    return n_writes, n_searches


def build_worldbench_stream(
    seed: int,
    template_name: str = "company",
    n_entities: int = 200,
    n_corrections: int = 10,
    n_questions: int = 20,
    entities_per_batch: int = 10,
) -> dict[str, Any]:
    """Build interleaved event stream for worldbench evaluation.

    Returns dict with keys: world, template, stream (list of events),
    template_name, seed. The stream interleaves ingest, corrections,
    and questions — the agent never knows what comes next.
    """
    tmpl = _TEMPLATES[template_name]()
    rng = Random(seed)
    world = tmpl.generate_world(seed, n_entities)

    # Generate corrections (mutates world state)
    corrections = tmpl.generate_corrections(world, rng, n_corrections)

    # Generate interleaved stream
    # For Inspect AI: we pre-generate with empty stored_names
    # (real detection happens at scoring time)
    stream = tmpl.generate_stream(
        world, rng, corrections,
        stored_names=set(),  # unknown at build time
        n_questions=n_questions,
        entities_per_batch=entities_per_batch,
    )

    return {
        "world": world,
        "template": tmpl,
        "stream": stream,
        "corrections": corrections,
        "template_name": template_name,
        "seed": seed,
    }


@solver
def worldbench_solver(
    stream_data: dict[str, Any],
    mem_budget: Any = None,
    backend: Any = None,
) -> Solver:
    """Interleaved stream solver: events arrive in unpredictable order.

    Processes ingest, correction, and question events from a single stream.
    Nuclear redaction after each event prevents context window exploitation.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        stream: list[dict] = stream_data["stream"]
        total_events = len(stream)

        answers: list[dict[str, Any]] = []
        qi = 0  # question counter

        for event_idx, event in enumerate(stream):
            msg_start = len(state.messages)
            event_type = event["type"]

            if event_type == "ingest":
                docs_text = _format_documents(event["documents"])
                state.messages.append(ChatMessageUser(
                    content=INGEST_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        documents=docs_text)))
                state = await generate(state, tool_calls="loop")
                # Nuclear redaction
                del state.messages[msg_start:]
                state.messages.append(ChatMessageUser(
                    content=f"[Event {event_idx+1}/{total_events} completed.]"))
                state.messages.append(ChatMessageAssistant(
                    content="Event processed."))

            elif event_type == "correction":
                state.messages.append(ChatMessageUser(
                    content=CORRECTION_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        notice=event["notice"])))
                state = await generate(state, tool_calls="loop")
                del state.messages[msg_start:]
                state.messages.append(ChatMessageUser(
                    content=f"[Event {event_idx+1}/{total_events} completed.]"))
                state.messages.append(ChatMessageAssistant(
                    content="Event processed."))

            elif event_type == "question":
                qi += 1
                state.messages.append(ChatMessageUser(
                    content=QUESTION_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        question=event["question"])))
                state = await generate(state, tool_calls="loop")

                answer = _extract_answer(state.messages)
                n_writes, n_searches = _count_tool_calls(
                    state.messages, msg_start)

                # Nuclear redaction
                del state.messages[msg_start:]
                state.messages.append(ChatMessageUser(
                    content=f"[Event {event_idx+1}/{total_events} completed.]"))
                state.messages.append(ChatMessageAssistant(
                    content="Event processed."))

                answers.append({
                    "task_id": qi - 1,
                    "question": event["question"],
                    "answer": answer,
                    "competency": event["competency"],
                    "purpose": event.get("purpose", ""),
                    "ground_truth": event["answer"],
                    "required_entities": event.get("required_entities", []),
                    "n_writes": n_writes,
                    "n_searches": n_searches,
                    "searched_before_answering": n_searches > 0,
                })

        writes_used = mem_budget.writes_used if mem_budget else 0
        state.store.set("benchmark_answers", answers)
        state.store.set("writes_used", writes_used)
        state.store.set("write_budget", mem_budget.total_writes
                        if mem_budget else 30)
        state.store.set("storage_coverage", 0.0)  # computed by scorer
        state.completed = True
        return state

    return solve


@task
def worldbench(
    seed: int | None = None,
    template: str = "company",
    n_entities: int = 200,
    n_corrections: int = 10,
    n_questions: int = 20,
    write_budget: int = 30,
    backend: str = "chromadb",
    entities_per_batch: int = 10,
) -> Task:
    """WorldTemplate-based memory management evaluation.

    Three-phase evaluation:
    1. INGEST: Agent receives entity documents in batches, stores under budget.
    2. CORRECTIONS: Agent receives correction notices, updates stored memories.
    3. QUESTIONS: Adaptive questions generated based on what was stored.

    Args:
        seed: Random seed for deterministic generation (required).
        template: World template ("company", "research", "city").
        n_entities: Number of entities to generate.
        n_corrections: Number of correction events.
        n_questions: Number of questions to generate.
        write_budget: Total memory writes allowed.
        backend: Memory backend ("chromadb" or "mem0").
        entities_per_batch: Entities per ingest batch.
    """
    if seed is None:
        raise ValueError(
            "seed is required. Pass -T seed=<int> when running inspect eval.")
    if template not in _TEMPLATES:
        raise ValueError(
            f"Unknown template '{template}'. Choose from: "
            f"{', '.join(_TEMPLATES)}")

    # V11: Use opaque hash for sample/task IDs — seed must not leak
    # to agent via sample.id or task.name
    run_hash = hashlib.sha256(
        f"{template}:{seed}:{n_entities}".encode()).hexdigest()[:12]

    stream_data = build_worldbench_stream(
        seed=seed,
        template_name=template,
        n_entities=n_entities,
        n_corrections=n_corrections,
        n_questions=n_questions,
        entities_per_batch=entities_per_batch,
    )

    memory_tools, mem_budget, backend_obj = create_memory_tools(
        budget=write_budget,
        backend_type=backend,
        collection_name=f"worldbench_{run_hash}",
    )

    system_msg = SYSTEM_PROMPT.format(budget=write_budget)
    sample = Sample(
        input="WorldBench Evaluation",
        target=str(seed),
        id=f"worldbench_{run_hash}",
        metadata={
            "seed": seed,
            "template": template,
            "n_entities": n_entities,
            "n_corrections": n_corrections,
            "n_questions": n_questions,
            "write_budget": write_budget,
        },
    )
    dataset = MemoryDataset([sample])

    from inspect_ai.solver import system_message as sys_msg
    from memorybench.worlds.eval_scorer import worldbench_scorer

    n_total_events = len(stream_data["stream"])

    return Task(
        dataset=dataset,
        solver=chain(
            sys_msg(system_msg),
            use_tools(memory_tools + [submit_answer()]),
            worldbench_solver(
                stream_data=stream_data,
                mem_budget=mem_budget,
                backend=backend_obj,
            ),
        ),
        scorer=worldbench_scorer(),
        message_limit=n_total_events * 20,
        name=f"worldbench_{run_hash}",
        metadata={
            "seed": seed,
            "template": template,
            "backend": backend,
            "write_budget": write_budget,
        },
    )
