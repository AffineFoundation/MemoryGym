"""Inspect AI task for WorldTemplate-based memory evaluation.

Usage:
    # Run with specific seed and template:
    inspect eval memorybench/worlds/eval_task.py -M openai/gpt-4o \
        -T seed=42 -T template=company

    # Run with mock backend (faster, for testing):
    inspect eval memorybench/worlds/eval_task.py -M openai/gpt-4o \
        -T seed=42 -T backend=mock -T n_entities=60
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
from memorybench.worlds.base import Correction, GeneratedQA, World, WorldTemplate
from memorybench.worlds.company import CompanyWorld
from memorybench.worlds.research import ResearchWorld
from memorybench.worlds.city import CityWorld

_TEMPLATES: dict[str, type[WorldTemplate]] = {
    "company": CompanyWorld,
    "research": ResearchWorld,
    "city": CityWorld,
}

SYSTEM_PROMPT = """You are participating in a memory management evaluation.

You will experience three phases:

1. **INGEST**: You will receive entity documents in batches. Decide what to store — \
you don't know what questions will be asked later.
2. **CORRECTIONS**: You will receive data correction notices. Update your stored \
memories accordingly.
3. **QUESTIONS**: Answer questions about previously seen entities. Search your \
memory and call submit_answer().

You have access to memory tools:
- memory_store(content, memory_id?): Store or update a memory (costs 1 write, \
budget: {budget})
- memory_search(query, top_k): Search stored memories (free)
- memory_get(memory_id): Retrieve a single memory by ID (free)
- memory_forget(memory_id): Remove a memory (free, no budget refund)
- memory_list(): List all memories (free)

IMPORTANT:
- Your write budget is LIMITED to {budget} writes total across ALL phases.
- During INGEST, store entity data proactively — you won't know what questions come.
- During CORRECTIONS, update relevant memories with corrected values.
- When answering, ALWAYS call submit_answer(answer="your answer").
- If you cannot answer from memory, call submit_answer(answer="I don't have \
enough information").
"""

INGEST_TEMPLATE = """=== Phase 1: INGEST — Batch {batch}/{total_batches} ===

**Documents:**
{documents}

No question for this batch. Read and store important entity data for future recall."""

CORRECTION_TEMPLATE = """=== Phase 2: CORRECTIONS — Batch {batch}/{total_batches} ===

**Correction Notices:**
{notices}

Update your stored memories with these corrected values."""

QUESTION_TEMPLATE = """=== Phase 3: QUESTION — {qnum}/{total_questions} ===

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


def build_worldbench_phases(
    seed: int,
    template_name: str = "company",
    n_entities: int = 200,
    n_corrections: int = 10,
    n_questions: int = 20,
    entities_per_batch: int = 10,
) -> dict[str, Any]:
    """Build phase data for a worldbench evaluation. Pure computation, no LLM.

    Returns dict with keys: world, template, ingest_batches, corrections,
    n_questions, entities_per_batch, template_name, seed.
    Questions are generated at runtime (post-storage) by the solver.
    """
    tmpl = _TEMPLATES[template_name]()
    rng = Random(seed)
    world = tmpl.generate_world(seed, n_entities)

    # Render ingest documents in batches
    ingest_batches: list[list[str]] = []
    batch: list[str] = []
    for entity in world.entities:
        batch.append(tmpl.render_document(entity, world.active_attrs, rng))
        if len(batch) >= entities_per_batch:
            ingest_batches.append(batch)
            batch = []
    if batch:
        ingest_batches.append(batch)

    # Generate corrections (mutates world state)
    corrections = tmpl.generate_corrections(world, rng, n_corrections)

    return {
        "world": world,
        "template": tmpl,
        "ingest_batches": ingest_batches,
        "corrections": corrections,
        "n_questions": n_questions,
        "entities_per_batch": entities_per_batch,
        "template_name": template_name,
        "seed": seed,
    }


@solver
def worldbench_solver(
    phases: dict[str, Any],
    mem_budget: Any = None,
    backend: Any = None,
) -> Solver:
    """Three-phase solver: INGEST → CORRECTIONS → QUESTIONS.

    Questions are generated dynamically after storage via
    detect_stored_entities + gen_adaptive_questions.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        world: World = phases["world"]
        tmpl: WorldTemplate = phases["template"]
        ingest_batches: list[list[str]] = phases["ingest_batches"]
        corrections: list[Correction] = phases["corrections"]
        n_questions: int = phases["n_questions"]

        answers: list[dict[str, Any]] = []
        total_batches = len(ingest_batches)

        # ── Phase 1: INGEST ──
        for i, batch_docs in enumerate(ingest_batches):
            msg_start = len(state.messages)
            docs_text = _format_documents(batch_docs)
            state.messages.append(ChatMessageUser(
                content=INGEST_TEMPLATE.format(
                    batch=i + 1, total_batches=total_batches,
                    documents=docs_text)))
            state = await generate(state, tool_calls="loop")
            # Nuclear redaction
            del state.messages[msg_start:]
            state.messages.append(ChatMessageUser(
                content=f"[Ingest batch {i+1}/{total_batches} completed. Redacted.]"))
            state.messages.append(ChatMessageAssistant(
                content=f"Ingest batch {i+1} of {total_batches} completed."))

        # ── Phase 2: CORRECTIONS ──
        if corrections:
            notices = "\n\n".join(c.notice for c in corrections)
            msg_start = len(state.messages)
            state.messages.append(ChatMessageUser(
                content=CORRECTION_TEMPLATE.format(
                    batch=1, total_batches=1, notices=notices)))
            state = await generate(state, tool_calls="loop")
            del state.messages[msg_start:]
            state.messages.append(ChatMessageUser(
                content="[Corrections phase completed. Redacted.]"))
            state.messages.append(ChatMessageAssistant(
                content="Corrections processed."))

        # ── Transition: detect storage → generate questions ──
        stored_contents = []
        if backend:
            entries = backend.list()
            stored_contents = [e["content"] for e in entries]
        stored_names, _missed = tmpl.detect_stored_entities(
            world, stored_contents)

        # Expose coverage and budget for scorer gating (Fix 4, Fix 5)
        coverage = len(stored_names) / len(world.entities)
        state.store.set("storage_coverage", coverage)
        state.store.set("write_budget", mem_budget.total_writes
                        if mem_budget else 30)

        rng = Random(phases["seed"] + 1)  # separate rng for questions
        qa_list: list[GeneratedQA] = tmpl.gen_adaptive_questions(
            world, rng,
            introduced=world.entities,
            stored_names=stored_names,
            n_questions=n_questions,
            corrections=corrections if corrections else None,
        )

        # ── Phase 3: QUESTIONS ──
        total_q = len(qa_list)
        for qi, qa in enumerate(qa_list):
            msg_start = len(state.messages)
            state.messages.append(ChatMessageUser(
                content=QUESTION_TEMPLATE.format(
                    qnum=qi + 1, total_questions=total_q,
                    question=qa.question)))
            state = await generate(state, tool_calls="loop")

            answer = _extract_answer(state.messages)
            n_writes, n_searches = _count_tool_calls(
                state.messages, msg_start)

            # Nuclear redaction
            del state.messages[msg_start:]
            state.messages.append(ChatMessageUser(
                content=f"[Question {qi+1}/{total_q} completed. Redacted.]"))
            state.messages.append(ChatMessageAssistant(
                content=f"Question {qi+1} of {total_q} completed."))

            answers.append({
                "task_id": qi,
                "question": qa.question,
                "answer": answer,
                "competency": qa.competency,
                "purpose": qa.purpose,
                "ground_truth": qa.answer,
                "required_entities": qa.required_entities,
                "n_writes": n_writes,
                "n_searches": n_searches,
                "searched_before_answering": n_searches > 0,
            })

        writes_used = mem_budget.writes_used if mem_budget else 0
        state.store.set("benchmark_answers", answers)
        state.store.set("writes_used", writes_used)
        state.store.set("n_ingest_batches", total_batches)
        state.store.set("n_corrections", len(corrections))
        state.store.set("n_questions", total_q)
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
        backend: Memory backend ("chromadb" or "mock").
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

    phases = build_worldbench_phases(
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

    n_total_tasks = len(phases["ingest_batches"]) + (
        1 if phases["corrections"] else 0) + n_questions

    return Task(
        dataset=dataset,
        solver=chain(
            sys_msg(system_msg),
            use_tools(memory_tools + [submit_answer()]),
            worldbench_solver(
                phases=phases,
                mem_budget=mem_budget,
                backend=backend_obj,
            ),
        ),
        scorer=worldbench_scorer(),
        message_limit=n_total_tasks * 20,
        name=f"worldbench_{run_hash}",
        metadata={
            "seed": seed,
            "template": template,
            "backend": backend,
            "write_budget": write_budget,
        },
    )
