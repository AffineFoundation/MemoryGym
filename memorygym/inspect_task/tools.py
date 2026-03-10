"""Inspect AI tools for MemoryGym memory operations."""

from __future__ import annotations

from inspect_ai.tool import Tool, ToolError, tool

from typing import Any

from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.memory.budget import MemoryBudget

# Type alias for any backend implementing store/search/get/forget/list
MemoryBackend = Any


def create_memory_tools(
    budget: int = 30,
    backend_type: str = "chromadb",
    collection_name: str = "memorygym",
    backend: MemoryBackend | None = None,
) -> tuple[list[Tool], MemoryBudget, MemoryBackend]:
    """Create all memory tools backed by a shared backend.

    Args:
        budget: Total write budget.
        backend_type: Backend type (currently only "chromadb").
        collection_name: Collection name for ChromaDB backend.
        backend: Pre-created backend (overrides backend_type).

    Returns:
        (list_of_tools, budget, backend) — budget and backend are returned
        for scorer / solver access.
    """
    if backend is None:
        backend = ChromaDBBackend(collection_name=collection_name)

    mem_budget = MemoryBudget(total_writes=budget)

    @tool
    def memory_store() -> Tool:
        """Store or update a memory entry. Costs 1 write from your budget."""
        async def execute(content: str, memory_id: str | None = None) -> str:
            """Save information to memory, or update an existing entry by ID.

            Args:
                content: The information to store.
                memory_id: Optional ID of an existing memory to update.
            """
            if len(content) > 2000:
                raise ToolError("Content exceeds 2000 character limit.")
            if not mem_budget.can_write():
                raise ToolError(
                    f"Write budget exhausted "
                    f"({mem_budget.writes_used}/{mem_budget.total_writes})."
                )
            if memory_id is not None:
                existing = backend.get(memory_id)
                if not existing:
                    raise ToolError(f"Memory {memory_id} not found.")
            mem_budget.consume_write()
            entry_id = backend.store(content, memory_id=memory_id)
            return (
                f"Stored (id={entry_id}). "
                f"Budget: {mem_budget.remaining()} writes remaining."
            )
        return execute

    @tool
    def memory_search() -> Tool:
        """Search stored memories by relevance. Free operation."""
        async def execute(query: str, top_k: int = 5) -> str:
            """Search your memory for relevant information.

            Args:
                query: Search query string.
                top_k: Maximum number of results (default 5).
            """
            results = backend.search(query, top_k=top_k)
            if not results:
                return "No matching memories found."
            parts = []
            for r in results:
                parts.append(f"[{r['id'][:8]}] {r['content']}")
            return "\n---\n".join(parts)
        return execute

    @tool
    def memory_get() -> Tool:
        """Retrieve a single memory by ID. Free operation."""
        async def execute(memory_id: str) -> str:
            """Get a specific memory entry by its ID.

            Args:
                memory_id: The ID of the memory to retrieve.
            """
            entry = backend.get(memory_id)
            if not entry:
                raise ToolError(f"Memory {memory_id} not found.")
            return f"[{entry['id']}] {entry['content']}"
        return execute

    @tool
    def memory_forget() -> Tool:
        """Delete a memory. Free operation (does NOT refund write budget)."""
        async def execute(memory_id: str) -> str:
            """Remove a memory entry.

            Args:
                memory_id: The ID of the memory to delete.
            """
            success = backend.forget(memory_id)
            if not success:
                raise ToolError(f"Memory {memory_id} not found.")
            return "Deleted."
        return execute

    @tool
    def memory_list() -> Tool:
        """List all stored memories. Free operation."""
        async def execute() -> str:
            """List all memories currently stored."""
            entries = backend.list()
            if not entries:
                return "No memories stored yet."
            parts = []
            for e in entries:
                parts.append(f"[{e['id'][:8]}] {e['content']}")
            return "\n".join(parts)
        return execute

    tools = [
        memory_store(),
        memory_search(),
        memory_get(),
        memory_forget(),
        memory_list(),
    ]
    return tools, mem_budget, backend


@tool
def submit_answer() -> Tool:
    """Submit your final answer for the current question."""
    async def execute(answer: str) -> str:
        """Submit your answer to the current question.

        Args:
            answer: Your final answer. Be precise and concise.
        """
        return f"ANSWER_SUBMITTED: {answer}"
    return execute
