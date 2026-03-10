"""Tests for MarkdownBackend: write/edit/read/search operations."""

import uuid
from pathlib import Path

from memorygym.memory.backends.markdown_backend import MarkdownBackend


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
        names = ["Alice", "Bob", "Charlie", "Diana", "Eve",
                 "Frank", "Grace", "Hank", "Iris", "Jack"]
        for name in names:
            b.write(f"{name} | salary: {hash(name) % 1000}k")
        found = 0
        for name in names:
            results = b.search(name, top_k=1)
            if results and name in results[0]["content"]:
                found += 1
        assert found >= 9, f"Recall {found}/10 too low"


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
