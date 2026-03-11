"""Budget management middleware for memory operations."""

from __future__ import annotations

from dataclasses import dataclass


class BudgetExhaustedError(Exception):
    """Raised when the write budget is exhausted."""


@dataclass
class MemoryBudget:
    """Tracks and enforces write budget limits."""

    total_writes: int = 30
    max_content_tokens: int = 500
    writes_used: int = 0

    def can_write(self) -> bool:
        return self.writes_used < self.total_writes

    def consume_write(self) -> None:
        if not self.can_write():
            raise BudgetExhaustedError(
                f"Write budget exhausted: {self.writes_used}/{self.total_writes}"
            )
        self.writes_used += 1

    def remaining(self) -> int:
        return max(0, self.total_writes - self.writes_used)

