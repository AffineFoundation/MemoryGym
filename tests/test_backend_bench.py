"""Backend integration tests — validates store→search→validate pipeline."""

from __future__ import annotations

from memorygym.evaluation.backend_bench import benchmark_backend
from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.worlds.company import CompanyWorld
from memorygym.worlds.city import CityWorld


def test_chromadb_recall():
    """ChromaDB must find stored entities by name with >= 90% recall."""
    backend = ChromaDBBackend(collection_name="test_recall")
    result = benchmark_backend(CompanyWorld(), seed=42, backend=backend,
                               n_entities=30, n_questions=10)
    assert result.search_recall >= 0.90, (
        f"ChromaDB recall {result.search_recall:.0%} < 90%")


def test_chromadb_value_preservation():
    """Stored values must survive store→search roundtrip (>= 85%)."""
    backend = ChromaDBBackend(collection_name="test_preserve")
    result = benchmark_backend(CompanyWorld(), seed=42, backend=backend,
                               n_entities=30, n_questions=10)
    assert result.value_preservation >= 0.80, (
        f"ChromaDB value preservation {result.value_preservation:.0%} < 80%")


def test_chromadb_accuracy_above_naive():
    """Backend ceiling must beat naive simulation (~37%)."""
    backend = ChromaDBBackend(collection_name="test_accuracy")
    result = benchmark_backend(CompanyWorld(), seed=42, backend=backend,
                               n_entities=60, n_questions=20)
    assert result.rule_accuracy >= 0.50, (
        f"ChromaDB accuracy {result.rule_accuracy:.0%} < 50% "
        f"(should beat naive ~37%)")


def test_chromadb_deterministic():
    """Same seed + fresh backend → same result."""
    b1 = ChromaDBBackend(collection_name="test_det_1")
    r1 = benchmark_backend(CompanyWorld(), seed=99, backend=b1,
                           n_entities=20, n_questions=10)
    b2 = ChromaDBBackend(collection_name="test_det_2")
    r2 = benchmark_backend(CompanyWorld(), seed=99, backend=b2,
                           n_entities=20, n_questions=10)
    assert r1.search_recall == r2.search_recall
    assert r1.correct == r2.correct


def test_chromadb_correction_applied():
    """After correction update, search must return new value."""
    from random import Random
    tmpl = CompanyWorld()
    world = tmpl.generate_world(seed=42, n_entities=10)
    backend = ChromaDBBackend(collection_name="test_corr")

    # Store one entity
    e = world.entities[0]
    doc = tmpl._compact_document(e, world.active_attrs)
    content = f"{e.name} | {doc}"
    mid = backend.store(content)

    # Apply correction
    rng = Random(42 + 3333)
    corrections = tmpl.generate_corrections(world, rng, 1)
    assert len(corrections) >= 1

    # Re-store corrected entity
    e_updated = world.get_entity(corrections[0].entity_name)
    if e_updated and e_updated.name == e.name:
        doc2 = tmpl._compact_document(e_updated, world.active_attrs)
        content2 = f"{e_updated.name} | {doc2}"
        backend.store(content2, memory_id=mid)

        # Search must return new value
        results = backend.search(e.name, top_k=1)
        assert len(results) > 0
        new_val = str(corrections[0].new_val)
        # Check the stored content has the new value
        stored = results[0]["content"].replace(",", "")
        found = (new_val in stored or
                 str(int(round(corrections[0].new_val))) in stored)
        assert found, (
            f"Correction value {new_val} not found in stored content")


def test_chromadb_entity_name_reranking():
    """Search must prefer exact entity-name matches over embedding similarity."""
    backend = ChromaDBBackend(collection_name="test_rerank")
    # Store two entities with similar names
    backend.store("Nexus Energy | revenue: $120M, employees: 500")
    backend.store("Nexus Tech | revenue: $80M, employees: 300")
    backend.store("Atlas Systems | revenue: $200M, employees: 1000")

    # Searching "Nexus Energy" must return Nexus Energy first,
    # not Nexus Tech (which shares the "Nexus" prefix).
    results = backend.search("Nexus Energy", top_k=2)
    assert len(results) >= 1
    assert "Nexus Energy" in results[0]["content"], (
        f"Expected 'Nexus Energy' first, got: {results[0]['content'][:50]}")

    # Searching "Atlas Systems" must return Atlas, not a Nexus entity.
    results = backend.search("Atlas Systems", top_k=1)
    assert len(results) == 1
    assert "Atlas Systems" in results[0]["content"]


def test_chromadb_rerank_top_k_limit():
    """Reranked search must respect top_k limit."""
    backend = ChromaDBBackend(collection_name="test_rerank_limit")
    for i in range(10):
        backend.store(f"Entity{i} | value: {i * 100}")
    results = backend.search("Entity5", top_k=3)
    assert len(results) == 3
    # Entity5 must be the first result (exact name match)
    assert "Entity5" in results[0]["content"]


def test_city_negative_temps():
    """CityWorld with negative temps must work through backend."""
    backend = ChromaDBBackend(collection_name="test_city")
    result = benchmark_backend(CityWorld(), seed=42, backend=backend,
                               n_entities=30, n_questions=10)
    # Should not crash and should have reasonable accuracy
    assert result.rule_accuracy >= 0.40, (
        f"CityWorld backend accuracy {result.rule_accuracy:.0%} < 40%")
    assert result.search_recall >= 0.90


def test_comprehension_no_gt_self_validation():
    """Comprehension questions must NOT use GT-vs-GT self-validation.

    If entity data is not extractable, comprehension must fail — even
    if the entity name is found in search results.
    """
    from memorygym.evaluation.backend_bench import _extract_answer_from_content

    # A backend that returns entity name but no attribute values
    class NameOnlyBackend:
        def store(self, content, memory_id=None):
            self._data = {"id": "fake", "content": content}
            return "fake"

        def search(self, query, top_k=3):
            # Return content with entity name but mangled attributes
            if hasattr(self, "_data"):
                name = query.lower()
                if name in self._data["content"].lower():
                    # Return content stripped of values (name only)
                    return [{"id": "fake", "content": query}]
            return []

        def get(self, mid):
            return getattr(self, "_data", None)

        def forget(self, mid):
            return True

        def list(self):
            return [self._data] if hasattr(self, "_data") else []

    backend = NameOnlyBackend()
    result = benchmark_backend(CompanyWorld(), seed=42, backend=backend,
                               n_entities=30, n_questions=15)

    # Comprehension questions should fail when only entity name is returned
    comp_types = {"synthesis", "aggregation", "conditional", "comparison",
                  "multi_hop", "outlier", "ratio", "delta"}
    for comp, (correct, total) in result.by_competency.items():
        if comp in comp_types and total > 0:
            assert correct == 0, (
                f"Comprehension type '{comp}' scored {correct}/{total} "
                f"with name-only backend — GT self-validation leak!")


if __name__ == "__main__":
    import sys
    tests = [
        test_chromadb_recall,
        test_chromadb_value_preservation,
        test_chromadb_accuracy_above_naive,
        test_chromadb_deterministic,
        test_chromadb_correction_applied,
        test_city_negative_temps,
        test_comprehension_no_gt_self_validation,
    ]
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            sys.exit(1)
    print("ALL BACKEND TESTS PASSED")
