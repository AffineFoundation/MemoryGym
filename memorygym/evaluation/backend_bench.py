"""Backend benchmark: deterministic perfect agent + real backend.

Measures the ceiling of each backend — "even if the agent makes perfect
storage decisions, what accuracy can this backend achieve?"

Fills the gap between simulation (100% recall assumption) and real agent
eval (agent + backend + search combined). No LLM involved — fully
deterministic and reproducible.

NOTE: backend_bench measures "perfect compression + backend" ceiling.
Real agents must also extract and compress data from narrative documents.
backend_bench ceiling − real score = agent compression/extraction gap.

NOTE: backend_bench uses compact KV format (not narrative documents).
This is intentional — it isolates backend quality from document parsing.

Usage:
    python -m memorygym.evaluation.backend_bench
    python -m memorygym.evaluation.backend_bench --backend chromadb --template company
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from random import Random
from typing import Any

from memorygym.evaluation.validators import AnswerValidator
from memorygym.worlds.base import WorldTemplate


@dataclass
class BackendBenchResult:
    """Result of one backend benchmark run."""

    template: str
    seed: int
    backend_type: str
    # Storage phase
    entities_stored: int
    store_failures: int
    # Search phase
    search_recall: float       # fraction of stored entities found by name search
    value_preservation: float  # fraction of values retrievable after roundtrip
    # Question answering phase
    rule_accuracy: float       # rule-based validator on extracted answers
    correct: int
    total: int
    by_competency: dict[str, tuple[int, int]] = field(default_factory=dict)


_VALIDATOR = AnswerValidator()

# Pattern for compact KV format: "label: value | label: value"
# Values may contain commas ($73,138.4M), so split on " | " not ","
_KV_RE = re.compile(r"([^:|]+):\s*(.+?)(?:\s*\||$)")


def _extract_answer_from_content(
    content: str, entity_name: str, attr_label: str,
) -> str | None:
    """Extract an attribute value from stored content by label matching.

    Looks for "label: value" patterns in the content. Returns the raw
    value string, or None if not found.
    """
    content_lower = content.lower()
    if entity_name.lower() not in content_lower:
        return None
    label_lower = attr_label.lower()
    for match in _KV_RE.finditer(content):
        key = match.group(1).strip().lower()
        if label_lower in key or key in label_lower:
            return match.group(2).strip()
    return None


def benchmark_backend(
    tmpl: WorldTemplate,
    seed: int,
    backend: Any,
    n_entities: int = 60,
    n_questions: int = 20,
    n_corrections: int = 5,
) -> BackendBenchResult:
    """Run deterministic perfect agent through real backend.

    Algorithm:
    1. Generate world, store ALL entities in backend (compact format)
    2. Generate corrections, UPDATE in backend (delete + re-store)
    3. For each question, search backend by entity name
    4. Extract answer from search results, validate with rule-based validator
    """
    world = tmpl.generate_world(seed=seed, n_entities=n_entities)
    rng = Random(seed)

    # Phase 1: Store all entities
    entity_ids: dict[str, str] = {}  # entity_name → memory_id
    store_failures = 0
    for e in world.entities:
        doc = tmpl._compact_document(e, world.active_attrs)
        content = f"{e.name} | {doc}"
        try:
            mid = backend.store(content)
            entity_ids[e.name] = mid
        except Exception:
            store_failures += 1

    # Phase 2: Apply corrections (delete old, store new)
    corrections = tmpl.generate_corrections(world, rng, n_corrections)
    for c in corrections:
        entity = world.get_entity(c.entity_name)
        if entity and c.entity_name in entity_ids:
            doc = tmpl._compact_document(entity, world.active_attrs)
            content = f"{entity.name} | {doc}"
            old_id = entity_ids[c.entity_name]
            try:
                backend.store(content, memory_id=old_id)
            except Exception:
                store_failures += 1

    # Phase 3: Measure search recall
    stored_count = len(entity_ids)
    search_hits = 0
    for name in entity_ids:
        results = backend.search(name, top_k=3)
        if any(name.lower() in r.get("content", "").lower() for r in results):
            search_hits += 1
    search_recall = search_hits / stored_count if stored_count else 0.0

    # Phase 4: Measure value preservation
    val_total = 0
    val_found = 0
    for e in world.entities:
        if e.name not in entity_ids:
            continue
        results = backend.search(e.name, top_k=1)
        if not results:
            continue
        content = results[0].get("content", "")
        for attr in world.active_attrs:
            val = e.get(attr)
            if val is None:
                continue
            val_total += 1
            # Check variants: raw, rounded, formatted
            variants = tmpl._numeric_variants(attr, val)
            cl = content.lower().replace(",", "")
            if any(v in cl for v in variants):
                val_found += 1
    value_preservation = val_found / val_total if val_total else 0.0

    # Phase 5: Generate questions and answer from search results
    stored_names = set(entity_ids.keys())
    rng_q = Random(seed + 7777)
    questions = tmpl.gen_adaptive_questions(
        world, rng_q, world.entities, stored_names, n_questions, corrections)

    correct = 0
    by_comp: dict[str, list[bool]] = {}

    for q in questions:
        ok = False

        if q.competency == "abstention":
            # Perfect agent with full storage knows to abstain
            ok = _VALIDATOR.validate(
                "I don't have enough information", q.answer, q.competency)
        elif q.competency in ("retrieval", "update"):
            # Search for the entity, extract value
            entity_name = q.required_entities[0]
            results = backend.search(entity_name, top_k=3)
            for r in results:
                content = r.get("content", "")
                if entity_name.lower() not in content.lower():
                    continue
                # Try to find the answer in the content
                # First: check if GT value appears directly
                gt_str = str(q.answer)
                if gt_str in content.replace(",", ""):
                    ok = True
                    break
                # Extract by attribute label matching
                for attr in world.active_attrs:
                    label = tmpl.attr_label(attr)
                    extracted = _extract_answer_from_content(
                        content, entity_name, label)
                    if extracted and _VALIDATOR.validate(
                            extracted, q.answer, q.competency):
                        ok = True
                        break
                if ok:
                    break
        elif q.competency in ("synthesis", "conditional", "comparison",
                              "multi_hop", "outlier",
                              "aggregation", "ratio", "delta"):
            # Comprehension: verify each required entity's source_attr
            # value is actually extractable from search results.
            # Previous: found entity name → GT-vs-GT (always true).
            # Now: found entity name + source_attr value extractable → ok.
            all_extractable = True
            for ename in q.required_entities:
                results = backend.search(ename, top_k=3)
                found = False
                for r in results:
                    content = r.get("content", "")
                    if ename.lower() not in content.lower():
                        continue
                    if q.source_attr:
                        label = tmpl.attr_label(q.source_attr)
                        extracted = _extract_answer_from_content(
                            content, ename, label)
                        if extracted:
                            found = True
                            break
                    else:
                        # ratio: source_attr="" (needs multiple attrs)
                        # Verify content has enough data (not just a name)
                        found = len(content) > 30
                        break
                if not found:
                    all_extractable = False
                    break
            if all_extractable:
                ok = True

        if ok:
            correct += 1
        by_comp.setdefault(q.competency, []).append(ok)

    total = len(questions)

    return BackendBenchResult(
        template=tmpl.name,
        seed=seed,
        backend_type=type(backend).__name__,
        entities_stored=stored_count,
        store_failures=store_failures,
        search_recall=search_recall,
        value_preservation=value_preservation,
        rule_accuracy=correct / total if total else 0.0,
        correct=correct,
        total=total,
        by_competency={c: (sum(v), len(v)) for c, v in by_comp.items()},
    )


def run_backend_bench(
    backend_type: str = "chromadb",
    template_name: str | None = None,
    n_seeds: int = 5,
) -> None:
    """Run backend benchmark and print results."""
    from memorygym.worlds import ALL_TEMPLATES

    templates = (
        {template_name: ALL_TEMPLATES[template_name]}
        if template_name else ALL_TEMPLATES
    )

    print("=" * 60)
    print(f"Backend Benchmark — {backend_type}")
    print("=" * 60)

    for tname, tcls in templates.items():
        tmpl = tcls()
        recalls = []
        preservations = []
        accuracies = []

        for seed in range(n_seeds):
            if backend_type == "chromadb":
                from memorygym.memory.backends.chromadb_backend import (
                    ChromaDBBackend,
                )
                backend = ChromaDBBackend(
                    collection_name=f"bench_{tname}_{seed}")
            elif backend_type == "mem0":
                from memorygym.memory.backends.mem0_backend import (
                    Mem0Backend,
                )
                backend = Mem0Backend(
                    user_id=f"bench_{tname}_{seed}")
            else:
                raise ValueError(f"Unsupported backend: {backend_type}")

            result = benchmark_backend(tmpl, seed, backend)
            recalls.append(result.search_recall)
            preservations.append(result.value_preservation)
            accuracies.append(result.rule_accuracy)

            print(f"  [{tname}] seed={seed}: recall={result.search_recall:.0%} "
                  f"preserve={result.value_preservation:.0%} "
                  f"accuracy={result.rule_accuracy:.0%}")

        avg_r = sum(recalls) / len(recalls)
        avg_p = sum(preservations) / len(preservations)
        avg_a = sum(accuracies) / len(accuracies)
        print(f"  [{tname}] AVG: recall={avg_r:.0%} "
              f"preserve={avg_p:.0%} accuracy={avg_a:.0%}\n")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--backend", default="chromadb")
    p.add_argument("--template", default=None)
    p.add_argument("--seeds", type=int, default=5)
    args = p.parse_args()
    run_backend_bench(args.backend, args.template, args.seeds)
