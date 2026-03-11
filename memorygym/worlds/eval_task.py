"""Inspect AI task for WorldTemplate-based memory evaluation.

Usage:
    # Run with specific seed and template:
    inspect eval memorygym/worlds/eval_task.py -M openai/gpt-4o \
        -T seed=42 -T template=company

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

from memorygym.inspect_task.tools import create_memory_tools, submit_answer
from . import ALL_TEMPLATES
from .base import World, WorldTemplate

_TEMPLATES = ALL_TEMPLATES

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

**Edit** — Edit existing content in your memory file (costs 1 write):
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

INGEST_TEMPLATE = """=== Event {event_num}/{total_events} [DOCUMENTS] ===

{budget_context}

**Documents:**
{documents}

No question. Read and store important entity data for future recall."""

CORRECTION_TEMPLATE = """=== Event {event_num}/{total_events} [CORRECTION] ===

**Correction Notice:**
{notice}

A correction has been issued. Decide how to handle it."""

QUESTION_TEMPLATE = """=== Event {event_num}/{total_events} [QUESTION] ===

**Question:**
{question}

Search your memory and call submit_answer(answer="...") with your final answer."""

NOISE_TEMPLATE = """=== Event {event_num}/{total_events} [INFO] ===

{noise_text}

This is supplementary information. Store only if relevant to your tasks."""


def _build_mem_summary(
    backend: Any, mem_budget: Any, event_idx: int, total_events: int,
) -> str:
    """Build memory state summary for selective redaction."""
    if backend is None:
        return f"[{event_idx+1}/{total_events} done]"
    entries = backend.list()
    remaining = mem_budget.remaining() if mem_budget else 0
    if entries:
        names = [e["content"].split("|")[0].strip() for e in entries]
        name_list = ", ".join(names[:30])
        if len(names) > 30:
            name_list += f" ... (+{len(names)-30} more)"
        return (
            f"[{event_idx+1}/{total_events} done]\n\n"
            f"Your memory contains {len(entries)} entries: {name_list}\n"
            f"Budget: {remaining} writes remaining."
        )
    return (
        f"[{event_idx+1}/{total_events} done]\n"
        f"Your memory is empty. Budget: {remaining} writes remaining."
    )


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
                if fn in ("Write", "Edit", "write_memory", "edit_memory", "memory_store"):
                    n_writes += 1
                elif fn in ("memory_search", "memory_list", "memory_get", "Read", "read_memory"):
                    n_searches += 1
    return n_writes, n_searches


def build_worldbench_stream(
    seed: int,
    template_name: str = "company",
    n_entities: int = 60,
    n_corrections: int = 5,
    n_questions: int = 20,
    entities_per_batch: int = 10,
) -> dict[str, Any]:
    """Build interleaved event stream for worldbench evaluation.

    Returns dict with keys: world, template, stream (list of events),
    template_name, seed. The stream interleaves ingest, corrections,
    and questions — the agent never knows what comes next.
    """
    tmpl = _TEMPLATES[template_name]()
    world = tmpl.generate_world(seed, n_entities, eval_salt=1)

    # Generate corrections (mutates world state)
    rng_correct = Random(seed + 3333)
    corrections = tmpl.generate_corrections(world, rng_correct, n_corrections)

    # Implicit contradictions (~30% of correction count)
    n_contras = max(1, n_corrections // 3)
    exclude_corrected = {c.entity_name for c in corrections}
    rng_contra = Random(seed + 7373)
    contradictions = tmpl.generate_contradictions(
        world, rng_contra, n_contras,
        exclude_entities=exclude_corrected)

    # Generate interleaved stream
    # For Inspect AI: we pre-generate with empty stored_names
    # (real detection happens at scoring time)
    rng_stream = Random(seed + 5555)
    stream = tmpl.generate_stream(
        world, rng_stream, corrections,
        stored_names=set(),  # unknown at build time
        n_questions=n_questions,
        entities_per_batch=entities_per_batch,
        contradictions=contradictions,
    )

    return {
        "world": world,
        "template": tmpl,
        "stream": stream,
        "corrections": corrections,
        "contradictions": contradictions,
        "template_name": template_name,
        "seed": seed,
    }


@solver
def worldbench_solver(
    stream_data: dict[str, Any],
    mem_budget: Any = None,
    backend: Any = None,
    no_redaction: bool = False,
) -> Solver:
    """Interleaved stream solver: events arrive in unpredictable order.

    Processes ingest, correction, and question events from a single stream.
    Nuclear redaction after each event prevents context window exploitation.

    Comprehension questions are adaptively replaced at runtime: if required
    entities are not in the backend, a new question is generated from
    entities the agent actually stored.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        stream: list[dict] = stream_data["stream"]
        world: World = stream_data["world"]
        tmpl: WorldTemplate = stream_data["template"]
        total_events = len(stream)

        answers: list[dict[str, Any]] = []
        qi = 0  # question counter

        # Precompute stream stats for dynamic budget context
        total_entities = sum(
            len(e.get("entity_names", []))
            for e in stream if e["type"] == "ingest"
        )
        entities_seen = 0

        # Anchor: keep only initial messages (system prompt + sample input).
        # After each event, delete everything past this point and add 2
        # placeholder messages. Matches stream_agent.py behavior — agent
        # sees a clean context each event, no history accumulation.
        initial_len = len(state.messages)

        for event_idx, event in enumerate(stream):
            msg_start = len(state.messages)
            event_type = event["type"]

            if event_type == "session_break":
                # Clear conversation context, keep memory backend
                del state.messages[initial_len:]
                session_id = event.get("session_id", 2)
                total_sess = event.get("total_sessions", 2)
                state.messages.append(ChatMessageUser(
                    content=f"[Session {session_id}/{total_sess} begins. "
                            f"Your conversation context has been reset. "
                            f"Your memory backend is preserved — use "
                            f"memory_search to recall stored data.]"))
                state.messages.append(ChatMessageAssistant(
                    content="Understood. Starting new session."))
                continue

            if event_type == "ingest":
                n_ents = len(event.get("entity_names", []))
                remaining = mem_budget.remaining() if mem_budget else 0
                budget_context = (
                    f"⚠️ Budget: {remaining}/"
                    f"{mem_budget.total_writes if mem_budget else 0} "
                    f"writes remaining. "
                    f"Entities seen so far: {entities_seen} (more may follow). "
                    f"Be selective — store what matters most."
                )
                entities_seen += n_ents
                docs_text = _format_documents(event["documents"])
                state.messages.append(ChatMessageUser(
                    content=INGEST_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        documents=docs_text,
                        budget_context=budget_context)))
                state = await generate(state, tool_calls="loop")
                if not no_redaction:
                    del state.messages[initial_len:]
                    mem_summary = _build_mem_summary(
                        backend, mem_budget, event_idx, total_events)
                    state.messages.append(ChatMessageUser(
                        content=mem_summary))
                    state.messages.append(ChatMessageAssistant(
                        content="OK."))

            elif event_type == "correction":
                state.messages.append(ChatMessageUser(
                    content=CORRECTION_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        notice=event["notice"])))
                state = await generate(state, tool_calls="loop")
                if not no_redaction:
                    del state.messages[initial_len:]
                    mem_summary = _build_mem_summary(
                        backend, mem_budget, event_idx, total_events)
                    state.messages.append(ChatMessageUser(
                        content=mem_summary))
                    state.messages.append(ChatMessageAssistant(
                        content="OK."))

            elif event_type == "question":
                qi += 1
                # Adaptive comprehension: replace questions whose
                # required entities aren't stored in the backend.
                if backend is not None:
                    stored_contents = [
                        e["content"] for e in backend.list()]
                    event = tmpl.maybe_replace_comprehension(
                        event, world, stored_contents,
                        rng_seed=stream_data["seed"] + event_idx,
                    )
                state.messages.append(ChatMessageUser(
                    content=QUESTION_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        question=event["question"])))
                state = await generate(state, tool_calls="loop")

                answer = _extract_answer(state.messages)
                n_writes, n_searches = _count_tool_calls(
                    state.messages, msg_start)

                if not no_redaction:
                    del state.messages[initial_len:]
                    mem_summary = _build_mem_summary(
                        backend, mem_budget, event_idx, total_events)
                    state.messages.append(ChatMessageUser(
                        content=mem_summary))
                    state.messages.append(ChatMessageAssistant(
                        content="OK."))

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

            elif event_type == "noise":
                state.messages.append(ChatMessageUser(
                    content=NOISE_TEMPLATE.format(
                        event_num=event_idx + 1, total_events=total_events,
                        noise_text=event["document"])))
                state = await generate(state, tool_calls="loop")
                if not no_redaction:
                    del state.messages[initial_len:]
                    mem_summary = _build_mem_summary(
                        backend, mem_budget, event_idx, total_events)
                    state.messages.append(ChatMessageUser(
                        content=mem_summary))
                    state.messages.append(ChatMessageAssistant(
                        content="OK."))

        writes_used = mem_budget.writes_used if mem_budget else 0

        # Detect stored entities for scoring
        n_entities = len(world.entities)
        stored_count = 0
        if backend is not None:
            stored_contents = [e["content"] for e in backend.list()]
            stored_names, _ = tmpl.detect_stored_entities(
                world, stored_contents)
            stored_count = len(stored_names)

        state.store.set("benchmark_answers", answers)
        state.store.set("writes_used", writes_used)
        state.store.set("write_budget", mem_budget.total_writes
                        if mem_budget else 30)
        state.store.set("n_entities", n_entities)
        state.store.set("stored_count", stored_count)
        state.completed = True
        return state

    return solve


@task
def worldbench(
    seed: int | None = None,
    template: str = "company",
    tier: str | None = None,
    n_entities: int | None = None,
    n_corrections: int | None = None,
    n_questions: int | None = None,
    write_budget: int | None = None,
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
        template: World template ("company", "research", "city", etc.).
        tier: Evaluation tier (lite/standard/hard/multi). Sets defaults
            for n_entities, n_corrections, n_questions, write_budget.
            Individual params override tier values.
        n_entities: Number of entities to generate.
        n_corrections: Number of correction events.
        n_questions: Number of questions to generate.
        write_budget: Total memory writes allowed.
        backend: Memory backend ("chromadb").
        entities_per_batch: Entities per ingest batch.
    """
    from memorygym.protocol import TIERS

    if seed is None:
        raise ValueError(
            "seed is required. Pass -T seed=<int> when running inspect eval.")
    if template not in _TEMPLATES:
        raise ValueError(
            f"Unknown template '{template}'. Choose from: "
            f"{', '.join(_TEMPLATES)}")

    # Resolve tier → defaults, then override with explicit params
    if tier is not None:
        if tier not in TIERS:
            raise ValueError(
                f"Unknown tier '{tier}'. Choose from: "
                f"{', '.join(TIERS)}")
        tc = TIERS[tier]
        n_entities = n_entities or tc["entities"]
        n_corrections = n_corrections or tc["corrections"]
        n_questions = n_questions or tc["questions"]
        write_budget = write_budget or tc["write_budget"]
    else:
        n_entities = n_entities or 60
        n_corrections = n_corrections or 5
        n_questions = n_questions or 20
        write_budget = write_budget or 30

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
    from .eval_scorer import worldbench_scorer

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
