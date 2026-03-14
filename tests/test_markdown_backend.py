"""Tests for MarkdownBackend: write/edit/read/search operations."""

import uuid
from pathlib import Path

import pytest

from memorygym.memory.backends.markdown_backend import MarkdownBackend

pytestmark = pytest.mark.slow  # ChromaDB embedding init ~3s per test


def _fresh_backend(tmp_path: Path | None = None) -> MarkdownBackend:
    """Create a backend with a unique temp directory."""
    if tmp_path is None:
        tmp_path = Path(f"/tmp/memorygym_test_{uuid.uuid4().hex[:8]}")
    return MarkdownBackend(memory_dir=tmp_path)


class TestWrite:
    def test_write_appends(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Alice | salary: 100k")
        b.write("Bob | salary: 200k")
        content = b.read()
        assert "Alice" in content
        assert "Bob" in content

    def test_write_returns_line_range(self, tmp_path):
        b = _fresh_backend(tmp_path)
        result = b.write("First line")
        assert "lines" in result
        assert "1" in result

    def test_write_reindexes(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Alice salary 100k")
        results = b.search("Alice")
        assert len(results) >= 1
        assert "Alice" in results[0]["content"]


class TestEdit:
    def test_edit_replaces_text(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Alice | salary: 100k")
        ok = b.edit("100k", "120k")
        assert ok
        assert "120k" in b.read()
        assert "100k" not in b.read()

    def test_edit_not_found(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Alice | salary: 100k")
        ok = b.edit("nonexistent text", "replacement")
        assert not ok

    def test_edit_reindexes(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Alice salary 100k")
        b.edit("100k", "120k")
        results = b.search("120k")
        assert len(results) >= 1
        assert "120k" in results[0]["content"]


class TestRead:
    def test_read_full(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Line one")
        b.write("Line two")
        content = b.read()
        assert "Line one" in content
        assert "Line two" in content

    def test_read_empty(self, tmp_path):
        b = _fresh_backend(tmp_path)
        assert b.read() == ""

    def test_read_line_range(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Line1\nLine2\nLine3\nLine4\nLine5")
        partial = b.read(start_line=2, num_lines=2)
        assert "Line2" in partial
        assert "Line3" in partial


class TestSearch:
    def test_search_finds_relevant(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Alice | salary: 100k | department: Engineering")
        b.write("Bob | salary: 200k | department: Marketing")
        b.write("Charlie | salary: 150k | department: Sales")
        results = b.search("Alice")
        assert len(results) >= 1
        assert "Alice" in results[0]["content"]

    def test_search_empty_backend(self, tmp_path):
        b = _fresh_backend(tmp_path)
        assert b.search("anything") == []

    def test_search_top_k(self, tmp_path):
        b = _fresh_backend(tmp_path)
        for i in range(10):
            b.write(f"Entity {i} | value: {i * 100}")
        results = b.search("Entity", top_k=3)
        assert len(results) == 3

    def test_search_recall(self, tmp_path):
        """Hybrid search should find entities by name with high recall."""
        b = _fresh_backend(tmp_path)
        # Use longer, more distinctive names to avoid embedding ambiguity
        names = ["Alice Johnson", "Robert Chen", "Charlotte Davis",
                 "Diana Patel", "Evelyn Torres", "Franklin Moore",
                 "Grace Nakamura", "Henrik Olsen", "Isabella Rivera",
                 "Jackson Wright"]
        for name in names:
            b.write(f"{name} | salary: {hash(name) % 1000}k")
        found = 0
        for name in names:
            results = b.search(name, top_k=1)
            if results and name in results[0]["content"]:
                found += 1
        assert found >= 7, f"Recall {found}/10 too low"


class TestCompatibility:
    def test_store_returns_id(self, tmp_path):
        b = _fresh_backend(tmp_path)
        mid = b.store("test content")
        assert mid.startswith("md_")

    def test_list_returns_paragraphs(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("Para one")
        b.write("Para two")
        entries = b.list()
        assert len(entries) == 2
        assert entries[0]["content"] == "Para one"

    def test_clear(self, tmp_path):
        b = _fresh_backend(tmp_path)
        b.write("some data")
        b.clear()
        assert b.read() == ""
        assert b.list() == []


class TestTemporalDecay:
    def test_edited_paragraph_ranks_higher(self, tmp_path):
        """After edit, updated paragraph should rank first in search."""
        b = _fresh_backend(tmp_path)
        b.write("Entity A | revenue: 100")
        b.write("Entity B | revenue: 200")
        b.write("Entity C | revenue: 300")
        # Edit A's value
        b.edit("revenue: 100", "revenue: 999")
        results = b.search("Entity A", top_k=3)
        assert len(results) > 0
        assert "999" in results[0]["content"]

    def test_newer_write_ranks_higher(self, tmp_path):
        """Most recent write should rank above older identical-relevance."""
        b = _fresh_backend(tmp_path)
        b.write("Company Alpha | revenue: 500")
        b.write("Company Beta | revenue: 600")
        # Write another Alpha entry (newer)
        b.write("Company Alpha | updated revenue: 800")
        results = b.search("Company Alpha", top_k=3)
        assert len(results) > 0
        # Newest Alpha entry should be first
        assert "800" in results[0]["content"]

    def test_decay_does_not_break_relevance(self, tmp_path):
        """Decay should not override strong relevance mismatch."""
        b = _fresh_backend(tmp_path)
        # Write irrelevant content last (newest)
        b.write("Entity X | salary: 100k, department: engineering")
        b.write("Entity Y | salary: 200k, department: marketing")
        results = b.search("Entity X salary", top_k=1)
        assert len(results) > 0
        assert "Entity X" in results[0]["content"]


class TestRecallBenchmark:
    """Recall benchmarks matching ChromaDB test coverage."""

    def test_markdown_recall_top1(self, tmp_path):
        """Store 10 entities, search each by name — top-1 hit rate ≥ 80%."""
        b = _fresh_backend(tmp_path)
        entities = [
            "Alice | salary: 100k, department: engineering",
            "Bob | salary: 150k, department: marketing",
            "Charlie | salary: 120k, department: sales",
            "Diana | salary: 200k, department: finance",
            "Edward | salary: 90k, department: engineering",
            "Fiona | salary: 180k, department: marketing",
            "George | salary: 110k, department: sales",
            "Helen | salary: 160k, department: finance",
            "Ivan | salary: 130k, department: engineering",
            "Julia | salary: 140k, department: marketing",
        ]
        for e in entities:
            b.write(e)

        hits = 0
        for e in entities:
            name = e.split(" | ")[0]
            results = b.search(name, top_k=1)
            if results and name in results[0]["content"]:
                hits += 1
        assert hits >= 8, f"Top-1 recall {hits}/10, expected ≥ 8"

    def test_markdown_accuracy_real_world(self, tmp_path):
        """Search with attribute queries on real-world-like entities."""
        from random import Random
        from memorygym.simulation import TEMPLATES
        tmpl_cls = list(TEMPLATES.values())[0]
        tmpl = tmpl_cls()
        world = tmpl.generate_world(seed=42, n_entities=20, eval_salt=1)

        b = _fresh_backend(tmp_path)
        for ent in world.entities:
            compact = tmpl._compact_document(ent, world.active_attrs)
            b.write(f"{ent.name} | {compact}")

        # Search by entity name — check top-3 contains the entity
        # (top-1 is often wrong due to shared name components like "Holdings")
        rng = Random(42)
        sample = rng.sample(list(world.entities), min(10, len(world.entities)))
        hits = 0
        for ent in sample:
            results = b.search(ent.name, top_k=3)
            if any(ent.name in r["content"] for r in results):
                hits += 1
        assert hits >= 5, f"Real-world top-3 recall {hits}/{len(sample)}, expected ≥ 5"
