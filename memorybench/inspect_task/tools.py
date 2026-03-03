"""Inspect AI tools for MemoryBench memory operations."""

from __future__ import annotations

from inspect_ai.tool import Tool, ToolError, tool

from memorybench.memory.backends.chromadb_backend import ChromaDBBackend
from memorybench.memory.backends.mock_backend import MockBackend
from memorybench.memory.budget import BudgetExhaustedError, MemoryBudget


def create_memory_tools(
    budget: int = 30,
    backend_type: str = "chromadb",
    collection_name: str = "memorybench",
) -> tuple[list[Tool], MemoryBudget]:
    """Create all 5 memory tools backed by a shared backend.

    Returns:
        (list_of_tools, budget) — budget is returned for scorer access.
    """
    if backend_type == "chromadb":
        backend = ChromaDBBackend(collection_name=collection_name)
    else:
        backend = MockBackend()

    mem_budget = MemoryBudget(total_writes=budget)

    @tool
    def memory_write() -> Tool:
        """Store a new memory entry. Costs 1 write from your budget."""
        async def execute(content: str) -> str:
            """Save information to memory.

            Args:
                content: The information to store.
            """
            if not mem_budget.can_write():
                raise ToolError(
                    f"Write budget exhausted "
                    f"({mem_budget.writes_used}/{mem_budget.total_writes})."
                )
            mem_budget.consume_write()
            entry_id = backend.add(content)
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
    def memory_update() -> Tool:
        """Update an existing memory. Costs 1 write from your budget."""
        async def execute(memory_id: str, content: str) -> str:
            """Replace an existing memory's content.

            Args:
                memory_id: The ID of the memory to update.
                content: The new content.
            """
            if not mem_budget.can_write():
                raise ToolError(
                    f"Write budget exhausted "
                    f"({mem_budget.writes_used}/{mem_budget.total_writes})."
                )
            mem_budget.consume_write()
            success = backend.update(memory_id, content)
            if not success:
                mem_budget.writes_used -= 1  # refund
                raise ToolError(f"Memory {memory_id} not found.")
            return (
                f"Updated. Budget: {mem_budget.remaining()} writes remaining."
            )
        return execute

    @tool
    def memory_delete() -> Tool:
        """Delete a memory. Free operation (does NOT refund write budget)."""
        async def execute(memory_id: str) -> str:
            """Remove a memory entry.

            Args:
                memory_id: The ID of the memory to delete.
            """
            success = backend.delete(memory_id)
            if not success:
                raise ToolError(f"Memory {memory_id} not found.")
            return "Deleted."
        return execute

    @tool
    def memory_list() -> Tool:
        """List all stored memories. Free operation."""
        async def execute() -> str:
            """List all memories currently stored."""
            entries = backend.list_all()
            if not entries:
                return "No memories stored yet."
            parts = []
            for e in entries:
                parts.append(f"[{e['id'][:8]}] {e['content'][:100]}")
            return "\n".join(parts)
        return execute

    tools = [
        memory_write(),
        memory_search(),
        memory_update(),
        memory_delete(),
        memory_list(),
    ]
    return tools, mem_budget


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
