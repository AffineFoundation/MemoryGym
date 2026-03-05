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
    """Substring-based memory backend matching mem0 interface."""

    def __init__(self) -> None:
        self.entries: list[MemoryEntry] = []

    def store(self, content: str, memory_id: str | None = None) -> str:
        """Store or update a memory entry. Returns the entry ID."""
        if memory_id is not None:
            for e in self.entries:
                if e.id == memory_id:
                    e.content = content
                    return memory_id
            # ID not found — fall through to create new entry with this ID
            self.entries.append(MemoryEntry(
                id=memory_id,
                content=content,
                created_at=datetime.now(timezone.utc).isoformat(),
            ))
            return memory_id
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

    def get(self, memory_id: str) -> dict | None:
        """Retrieve a single entry by ID."""
        for e in self.entries:
            if e.id == memory_id:
                return {
                    "id": e.id, "content": e.content,
                    "created_at": e.created_at,
                }
        return None

    def forget(self, memory_id: str) -> bool:
        for i, e in enumerate(self.entries):
            if e.id == memory_id:
                self.entries.pop(i)
                return True
        return False

    def list(self) -> list[dict]:
        return [
            {"id": e.id, "content": e.content, "created_at": e.created_at}
            for e in self.entries
        ]

    def clear(self) -> None:
        self.entries.clear()
