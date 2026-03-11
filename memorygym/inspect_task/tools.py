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

    @tool(name="Write")
    def write_memory() -> Tool:
        """Write information to your memory file. Costs 1 write from budget."""
        async def execute(content: str) -> str:
            """Append information to your memory file.

            Args:
                content: The information to write.
            """
            if len(content) > 2000:
                raise ToolError("Content exceeds 2000 character limit.")
            if not mem_budget.can_write():
                raise ToolError(
                    f"Write budget exhausted "
                    f"({mem_budget.writes_used}/{mem_budget.total_writes})."
                )
            mem_budget.consume_write()
            if hasattr(backend, "write"):
                line_range = backend.write(content)
                return (
                    f"Written ({line_range}). "
                    f"Budget: {mem_budget.remaining()} writes remaining."
                )
            entry_id = backend.store(content)
            return (
                f"Stored (id={entry_id}). "
                f"Budget: {mem_budget.remaining()} writes remaining."
            )
        return execute

    @tool(name="Edit")
    def edit_memory() -> Tool:
        """Edit existing content in your memory file. Costs 1 write."""
        async def execute(old_text: str, new_text: str) -> str:
            """Replace existing text in your memory file.

            Args:
                old_text: The text to find and replace.
                new_text: The replacement text.
            """
            if not mem_budget.can_write():
                raise ToolError(
                    f"Write budget exhausted "
                    f"({mem_budget.writes_used}/{mem_budget.total_writes})."
                )
            mem_budget.consume_write()
            if hasattr(backend, "edit"):
                ok = backend.edit(old_text, new_text)
                if not ok:
                    mem_budget.writes_used -= 1
                    raise ToolError("Text not found in memory.")
                return (
                    f"Edited. "
                    f"Budget: {mem_budget.remaining()} writes remaining."
                )
            # Fallback for ChromaDB
            results = backend.search(old_text, top_k=1)
            if results and old_text in results[0]["content"]:
                backend.forget(results[0]["id"])
                content = results[0]["content"].replace(old_text, new_text, 1)
                backend.store(content)
                return (
                    f"Edited. "
                    f"Budget: {mem_budget.remaining()} writes remaining."
                )
            mem_budget.writes_used -= 1
            raise ToolError("Text not found in memory.")
        return execute

    @tool(name="Read")
    def read_memory() -> Tool:
        """Read your memory file contents. Free operation."""
        async def execute(start_line: int | None = None,
                         num_lines: int | None = None) -> str:
            """Read your memory file, optionally a specific line range.

            Args:
                start_line: Line number to start reading from (1-indexed).
                num_lines: Number of lines to read.
            """
            if hasattr(backend, "read"):
                content = backend.read(start_line=start_line,
                                       num_lines=num_lines)
                if not content:
                    return "Memory is empty."
                return content
            entries = backend.list()
            if not entries:
                return "No memories stored yet."
            parts = [f"[{e['id'][:8]}] {e['content']}" for e in entries]
            return "\n".join(parts)
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

    tools = [
        write_memory(),
        edit_memory(),
        read_memory(),
        memory_search(),
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
