"""Memory store: simple substring-search storage with write budget."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryStore:
    entries: list[str] = field(default_factory=list)
    writes_used: int = 0
    max_writes: int = 999999
    max_writes_per_task: int = 999999
    _writes_this_task: int = field(default=0, repr=False)

    def reset_task(self) -> None:
        """Call at the start of each task to reset per-task counter."""
        self._writes_this_task = 0

    def write(self, content: str) -> bool:
        if (self.writes_used >= self.max_writes
                or self._writes_this_task >= self.max_writes_per_task):
            return False
        self.entries.append(content)
        self.writes_used += 1
        self._writes_this_task += 1
        return True

    def search(self, query: str) -> list[str]:
        q = query.lower()
        return [e for e in self.entries if q in e.lower()]
