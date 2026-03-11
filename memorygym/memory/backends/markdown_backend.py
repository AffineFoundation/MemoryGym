"""Markdown-file memory backend: OpenClaw-compatible Write/Edit/Read + hybrid search."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"\w+", text.lower())


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (double-newline separated)."""
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


class MarkdownBackend:
    """OpenClaw-compatible: Markdown file + hybrid search.

    Storage is a single MEMORY.md file. Each write() appends a paragraph.
    Search indexes paragraphs individually, combining:
    - Sentence-transformer embeddings (70% weight)
    - BM25 keyword matching (30% weight)
    - Reciprocal Rank Fusion for reranking
    """

    def __init__(
        self,
        memory_dir: str | Path | None = None,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        if memory_dir is None:
            memory_dir = Path(f"/tmp/memorygym_md_{uuid.uuid4().hex[:8]}")
        self._dir = Path(memory_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "MEMORY.md"
        if not self._file.exists():
            self._file.write_text("")

        self._model = SentenceTransformer(model_name)
        self._paragraphs: list[str] = []
        self._embeddings: np.ndarray | None = None
        self._bm25: BM25Okapi | None = None
        self._reindex()

    def _reindex(self) -> None:
        """Rebuild paragraph-level index from current file content."""
        content = self._file.read_text()
        self._paragraphs = _split_paragraphs(content) if content.strip() else []
        if self._paragraphs:
            self._embeddings = self._model.encode(
                self._paragraphs, convert_to_numpy=True)
            tokenized = [_tokenize(p) for p in self._paragraphs]
            self._bm25 = BM25Okapi(tokenized)
        else:
            self._embeddings = None
            self._bm25 = None

    def write(self, content: str) -> str:
        """Append content to MEMORY.md. Returns line range description."""
        current = self._file.read_text()
        start_line = current.count("\n") + 1 if current else 1
        separator = "\n\n" if current.strip() else ""
        self._file.write_text(current + separator + content)
        end_line = start_line + content.count("\n")
        self._reindex()
        return f"lines {start_line}-{end_line}"

    def edit(self, old_text: str, new_text: str) -> bool:
        """Replace first occurrence of old_text with new_text in MEMORY.md."""
        content = self._file.read_text()
        if old_text not in content:
            return False
        updated = content.replace(old_text, new_text, 1)
        self._file.write_text(updated)
        self._reindex()
        return True

    def read(self, start_line: int | None = None,
             num_lines: int | None = None) -> str:
        """Read MEMORY.md content, optionally a line range."""
        content = self._file.read_text()
        if start_line is None:
            return content
        lines = content.split("\n")
        start = max(0, start_line - 1)  # 1-indexed
        end = start + num_lines if num_lines else len(lines)
        return "\n".join(lines[start:end])

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Hybrid search: vector (70%) + BM25 (30%) with RRF reranking."""
        if not self._paragraphs or self._embeddings is None:
            return []

        n = len(self._paragraphs)
        k_rrf = 60  # RRF constant

        # Vector search: cosine similarity
        q_emb = self._model.encode([query], convert_to_numpy=True)
        cosine_sims = (self._embeddings @ q_emb.T).flatten()
        vec_ranks = np.argsort(-cosine_sims)  # descending

        # BM25 search
        bm25_scores = self._bm25.get_scores(_tokenize(query))
        bm25_ranks = np.argsort(-bm25_scores)  # descending

        # RRF fusion
        rrf_scores = np.zeros(n)
        for rank_pos, idx in enumerate(vec_ranks):
            rrf_scores[idx] += 0.7 / (k_rrf + rank_pos + 1)
        for rank_pos, idx in enumerate(bm25_ranks):
            rrf_scores[idx] += 0.3 / (k_rrf + rank_pos + 1)

        # Top-k by RRF score
        top_indices = np.argsort(-rrf_scores)[:top_k]

        results = []
        for idx in top_indices:
            if rrf_scores[idx] <= 0:
                continue
            results.append({
                "id": f"para_{idx}",
                "content": self._paragraphs[idx],
                "created_at": "",
            })
        return results

    # -- Compatibility with existing backend interface --

    def store(self, content: str, memory_id: str | None = None) -> str:
        """Compatibility: store = write. Returns a synthetic ID."""
        self.write(content)
        return f"md_{uuid.uuid4().hex[:8]}"

    def get(self, memory_id: str) -> dict | None:
        """Not directly supported in file-based backend."""
        return None

    def forget(self, memory_id: str) -> bool:
        """Not directly supported in file-based backend."""
        return False

    def list(self) -> list[dict]:
        """Return all paragraphs as entries."""
        return [
            {"id": f"para_{i}", "content": p, "created_at": ""}
            for i, p in enumerate(self._paragraphs)
        ]

    def clear(self) -> None:
        """Clear the memory file and index."""
        self._file.write_text("")
        self._reindex()

    def close(self) -> None:
        """Remove the temp directory if it exists under /tmp."""
        import shutil
        if self._dir.exists() and str(self._dir).startswith("/tmp/"):
            shutil.rmtree(self._dir, ignore_errors=True)
