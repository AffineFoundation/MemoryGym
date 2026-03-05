"""Real mem0 backend using the mem0ai Python SDK.

Requires: pip install mem0ai
"""

from __future__ import annotations

from mem0 import Memory


class Mem0Backend:
    """Production backend using mem0 (https://github.com/mem0ai/mem0).

    Delegates all operations to the mem0 SDK, mapping the MemoryBench
    backend interface to mem0's API.
    """

    def __init__(self, user_id: str = "memorybench") -> None:
        self._m = Memory()
        self._user_id = user_id

    def store(self, content: str, memory_id: str | None = None) -> str:
        """Store or update a memory entry. Returns the entry ID."""
        if memory_id is not None:
            self._m.update(memory_id, content)
            return memory_id
        result = self._m.add(content, user_id=self._user_id)
        return result["id"]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        results = self._m.search(query, user_id=self._user_id, limit=top_k)
        return [
            {"id": r["id"], "content": r["memory"], "created_at": r.get("created_at", "")}
            for r in results
        ]

    def get(self, memory_id: str) -> dict | None:
        """Retrieve a single entry by ID."""
        try:
            r = self._m.get(memory_id)
            if not r:
                return None
            return {"id": r["id"], "content": r["memory"], "created_at": r.get("created_at", "")}
        except Exception:
            return None

    def forget(self, memory_id: str) -> bool:
        try:
            self._m.delete(memory_id)
            return True
        except Exception:
            return False

    def list(self) -> list[dict]:
        results = self._m.get_all(user_id=self._user_id)
        return [
            {"id": r["id"], "content": r["memory"], "created_at": r.get("created_at", "")}
            for r in results
        ]

    def clear(self) -> None:
        self._m.delete_all(user_id=self._user_id)
