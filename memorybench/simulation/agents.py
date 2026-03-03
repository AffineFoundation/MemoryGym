"""Simulated agent strategies for MemoryBench PoC validation."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from memorybench.domains.base import Domain, Entity, QA, Task, TaskResult
from memorybench.evaluation.validators import AnswerValidator
from memorybench.memory.store import MemoryStore

_VALIDATOR = AnswerValidator()


# ── Trace types ──

@dataclass
class WriteOp:
    """A single memory write operation."""
    content_preview: str  # first 80 chars
    category: str  # "entity", "correction", "raw_doc", "distractor", "org_pattern"
    accepted: bool  # False if budget exhausted


@dataclass
class SearchOp:
    """A single memory search operation."""
    query: str
    n_results: int
    found_attr: bool = False  # was the required attribute present?


@dataclass
class TaskTrace:
    """Full trace of agent activity on a single task."""
    task_id: int
    domain: str
    writes: list[WriteOp] = field(default_factory=list)
    searches: list[SearchOp] = field(default_factory=list)
    budget_before: int = 0
    budget_after: int = 0
    n_docs_received: int = 0
    n_new_entities: int = 0
    # Process indicators (Phase 2)
    searched_before_answering: bool | None = None  # None = no question
    n_search_hits: int = 0
    stored_any: bool = False


# ── Helpers ──

def _word_match(pattern: str, text: str) -> bool:
    """Check if pattern appears as a whole word (not substring of another word)."""
    return bool(re.search(r'\b' + re.escape(pattern) + r'\b', text))


def _detect_asked_attr(question: str, domain: Domain,
                       entity_names: list[str] | None = None) -> str | None:
    """Detect which attribute a question is asking about.

    Strips entity names from the question first to avoid false matches.
    Priority: exact attr name match > longest synonym match.
    """
    q = question.lower()
    if entity_names:
        for name in entity_names:
            q = q.replace(name.lower(), "")
    for attr in domain.ALL_ATTRS:
        if _word_match(attr, q):
            return attr
    best_attr = None
    best_len = 0
    for attr in domain.ALL_ATTRS:
        syns = domain.ATTR_SYNONYMS.get(attr, {attr})
        for s in syns:
            if len(s) > best_len and _word_match(s, q):
                best_len = len(s)
                best_attr = attr
    return best_attr


def _answer_with_reason(
    qa: QA, search_fn: Callable[[str], list[str]],
    dom: Domain, strategy: str,
) -> tuple[Any, str, int]:
    """Answer a question, returning (answer, failure_reason, total_search_hits).

    failure_reason is "" on success.
    """
    total_hits = 0

    if qa.competency == "abstention":
        if strategy == "perfect":
            return "ABSTAIN", "", 0
        name = qa.required_entities[0]
        results = search_fn(name)
        total_hits = len(results)
        if strategy in ("strategic", "fixed"):
            return "ABSTAIN", "", total_hits
        # naive: entity found → abstain (recognises data gap);
        #        entity not found → hallucinate (no signal to detect gap)
        if results:
            return "ABSTAIN", "", total_hits
        return "HALLUCINATED", "naive_hallucinate", total_hits

    if qa.competency == "retrieval":
        name = qa.required_entities[0]
        results = search_fn(name)
        total_hits = len(results)
        if not results:
            return None, "no_entity_in_memory", 0
        asked = _detect_asked_attr(qa.question, dom, qa.required_entities)
        if asked and any(dom.has_attr_in_text(asked, r) for r in results):
            return qa.answer, "", total_hits
        if not asked:
            return qa.answer, "", total_hits
        return None, f"attr_missing:{asked}", total_hits

    if qa.competency == "synthesis":
        asked = _detect_asked_attr(qa.question, dom, qa.required_entities)
        for name in qa.required_entities:
            results = search_fn(name)
            total_hits += len(results)
            if not results:
                return None, f"no_entity_in_memory:{name}", total_hits
            if asked and not any(
                dom.has_attr_in_text(asked, r) for r in results
            ):
                return None, f"attr_missing:{asked}:{name}", total_hits
        return qa.answer, "", total_hits

    if qa.competency == "update":
        name = qa.required_entities[0]
        results = search_fn(name)
        total_hits = len(results)
        if not results:
            return None, "no_entity_in_memory", 0
        new_val_str = str(qa.answer)
        has_new_value = any(new_val_str in r for r in results)
        if not has_new_value:
            return None, "old_value_only", total_hits
        if strategy == "naive":
            return None, "naive_update_blocked", total_hits
        return qa.answer, "", total_hits

    if qa.competency == "cross_domain":
        for name in qa.required_entities:
            results = search_fn(name)
            total_hits += len(results)
            if not results:
                return None, f"no_entity_in_memory:{name}", total_hits
        if strategy in ("perfect", "strategic"):
            return qa.answer, "", total_hits
        return None, "strategy_incapable", total_hits

    return None, "unknown_competency", 0


def _guesser_answer(qa: QA, rng: random.Random) -> tuple[Any, str, int]:
    """Guesser strategy: no memory, blind guessing without competency knowledge.

    A realistic zero-memory baseline: the guesser cannot distinguish abstention
    from retrieval, so it picks a random response type for every question.
    This ensures guesser accuracy stays below 5%.
    """
    # Blind guess distribution: 55% number, 30% entity name, 15% abstain
    roll = rng.random()
    if roll < 0.55:
        return rng.randint(1, 100000), "guesser", 0
    elif roll < 0.85:
        if qa.required_entities:
            return rng.choice(qa.required_entities), "guesser", 0
        return rng.randint(1, 100000), "guesser", 0
    else:
        return "I don't have enough information", "guesser", 0


# Per-domain pattern keywords for fixed strategy.
# Each domain has recognisable vocabulary; the fixed agent stores any
# document that matches at least one keyword for ANY domain.
DOMAIN_PATTERNS = {
    "organization": [
        "earns", "years old", "team of", "experience",
        "performance score", "specialist", "serves in", "division",
    ],
    "research": [
        "citations", "h-index", "funding", "doctoral students",
        "review score", "published", "papers", "affiliated with",
    ],
    "logistics": [
        "unit price", "priced at", "weight", "lead time",
        "defect rate", "demand forecast", "stock", "sku",
    ],
}
# Flattened for O(1)-ish lookup
_ALL_FIXED_PATTERNS = [p for ps in DOMAIN_PATTERNS.values() for p in ps]


def _classify_doc(doc: str) -> str:
    """Classify a document for trace purposes."""
    dl = doc.lower()
    if "correction" in dl:
        return "correction"
    if any(kw in dl for kw in ("project brief", "meeting notice",
                                "workshop", "seminar", "supply order",
                                "shipment notice")):
        return "distractor"
    return "entity_doc"


def simulate_agent(
    strategy: str, tasks: list[Task], kbs: dict,
    dom_map: dict[str, Domain], updates: dict,
    seed: int, write_budget: int = 50,
    max_writes_per_task: int = 3,
) -> tuple[list[TaskResult], int, list[TaskTrace]]:
    """Simulate an agent strategy on a task stream.

    Returns (results, actual_writes_used, traces).
    """
    rng = random.Random(seed + 99999)
    max_w = 999999 if strategy == "perfect" else write_budget
    per_task = 999999 if strategy == "perfect" else max_writes_per_task
    memory = MemoryStore(max_writes=max_w, max_writes_per_task=per_task)
    results = []
    traces: list[TaskTrace] = []

    # Build entity lookup per domain
    entities_by_name: dict[str, tuple[Entity, str]] = {}
    for dname, kb in kbs.items():
        for e in kb["entities"]:
            entities_by_name[e.name] = (e, dname)

    for task in tasks:
        memory.reset_task()

        dom = dom_map.get(task.domain)
        active = kbs[task.domain]["active_attrs"] if task.domain in kbs else []

        if dom is None:
            dom = list(dom_map.values())[0]
            active = kbs[dom.name]["active_attrs"]

        trace = TaskTrace(
            task_id=task.task_id, domain=task.domain,
            budget_before=max_w - memory.writes_used,
            n_docs_received=len(task.documents),
            n_new_entities=len(task.new_entity_names),
        )

        # ── Store ──
        if strategy == "perfect":
            for doc in task.documents:
                ok = memory.write(doc)
                trace.writes.append(WriteOp(
                    doc[:80], _classify_doc(doc), ok))
            for name in task.new_entity_names:
                if name in entities_by_name:
                    e, _ = entities_by_name[name]
                    content = dom.format_structured(e, active)
                    ok = memory.write(content)
                    trace.writes.append(WriteOp(content[:80], "entity", ok))

        elif strategy == "strategic":
            # Priority: corrections first (remove stale + write fresh),
            # then new entities (skip if already stored).
            for doc in task.documents:
                if "correction" in doc.lower():
                    for ename in entities_by_name:
                        if ename in doc:
                            memory.entries = [
                                e for e in memory.entries if ename not in e
                            ]
                            ent, _ = entities_by_name[ename]
                            content = dom.format_structured(ent, active)
                            ok = memory.write(content)
                            trace.writes.append(WriteOp(
                                content[:80], "correction", ok))
                            break
            for name in task.new_entity_names:
                if name in entities_by_name:
                    # Skip if entity already stored
                    if memory.search(name):
                        continue
                    e, _ = entities_by_name[name]
                    content = dom.format_structured(e, active)
                    ok = memory.write(content)
                    trace.writes.append(WriteOp(content[:80], "entity", ok))

        elif strategy == "fixed":
            for doc in task.documents:
                doc_lower = doc.lower()
                if any(p in doc_lower for p in _ALL_FIXED_PATTERNS):
                    ok = memory.write(doc[:500])
                    trace.writes.append(WriteOp(
                        doc[:80], "pattern_match", ok))

        elif strategy == "naive":
            docs = list(task.documents)
            rng.shuffle(docs)
            for doc in docs:
                ok = memory.write(doc[:500])
                trace.writes.append(WriteOp(
                    doc[:80], _classify_doc(doc), ok))

        elif strategy == "guesser":
            pass  # guesser stores nothing

        trace.budget_after = max_w - memory.writes_used
        trace.stored_any = len(trace.writes) > 0 and any(
            w.accepted for w in trace.writes)

        # ── Answer ──
        if task.question is None:
            traces.append(trace)
            continue

        if strategy == "guesser":
            answer, reason, hits = _guesser_answer(task.question, rng)
            trace.searched_before_answering = False
            trace.n_search_hits = 0
        else:
            answer, reason, hits = _answer_with_reason(
                task.question, memory.search, dom, strategy,
            )
            # Process tracking: any search happened = searched_before_answering
            trace.searched_before_answering = hits > 0
            trace.n_search_hits = hits

        if strategy == "guesser":
            # Use validator to simulate real LLM evaluation path
            is_correct = _VALIDATOR.validate(
                str(answer), task.question.answer, task.question.competency)
        else:
            is_correct = (answer == task.question.answer)

        results.append(TaskResult(
            task_id=task.task_id,
            competency=task.question.competency,
            domain=task.domain,
            is_correct=is_correct,
            agent_answer=answer,
            expected_answer=task.question.answer,
            question_text=task.question.question,
            failure_reason=reason,
            search_hits=hits,
        ))
        traces.append(trace)

    return results, memory.writes_used, traces
