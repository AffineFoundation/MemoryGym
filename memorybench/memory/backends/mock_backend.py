"""Mock memory backend: substring search, for testing and simulation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class MemoryEntry:
    id: str
    content: str
    created_at: str


class MockBackend:
    """Substring-based memory backend matching PoC behavior."""

    def __init__(self) -> None:
        self.entries: list[MemoryEntry] = []

    def add(self, content: str) -> str:
        entry_id = str(uuid.uuid4())
        self.entries.append(MemoryEntry(
            id=entry_id,
            content=content,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        return entry_id

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        q = query.lower()
        results = []
        for e in self.entries:
            if q in e.content.lower():
                results.append({
                    "id": e.id, "content": e.content,
                    "created_at": e.created_at,
                })
        return results[:top_k]

    def update(self, entry_id: str, content: str) -> bool:
        for e in self.entries:
            if e.id == entry_id:
                e.content = content
                return True
        return False

    def delete(self, entry_id: str) -> bool:
        for i, e in enumerate(self.entries):
            if e.id == entry_id:
                self.entries.pop(i)
                return True
        return False

    def list_all(self) -> list[dict]:
        return [
            {"id": e.id, "content": e.content, "created_at": e.created_at}
            for e in self.entries
        ]

    def clear(self) -> None:
        self.entries.clear()
