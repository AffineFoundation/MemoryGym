"""MCP Memory Server: exposes 5 memory tools via FastMCP.

Usage:
    # With mock backend (testing):
    python -m memorybench.memory.mcp_server --backend mock

    # With chromadb backend (production):
    python -m memorybench.memory.mcp_server --backend chromadb --budget 30
"""

from __future__ import annotations

import argparse

from fastmcp import FastMCP

from memorybench.memory.budget import (
    BudgetExhaustedError,
    MemoryBudget,
)


def create_server(
    backend_type: str = "mock",
    budget: int = 30,
    max_content_tokens: int = 500,
) -> FastMCP:
    """Create and configure the MCP memory server."""
    mcp = FastMCP("memorybench-memory")

    # Initialize backend
    if backend_type == "chromadb":
        from memorybench.memory.backends.chromadb_backend import ChromaDBBackend
        backend = ChromaDBBackend()
    else:
        from memorybench.memory.backends.mock_backend import MockBackend
        backend = MockBackend()

    mem_budget = MemoryBudget(
        total_writes=budget,
        max_content_tokens=max_content_tokens,
    )

    @mcp.tool()
    def memory_write(content: str) -> str:
        """Store a new memory entry. Costs 1 write from your budget.

        Args:
            content: The information to store (max 500 tokens).

        Returns:
            The memory ID for future reference, or an error message.
        """
        if len(content.split()) > mem_budget.max_content_tokens:
            return f"ERROR: Content exceeds {mem_budget.max_content_tokens} token limit."
        try:
            mem_budget.consume_write()
        except BudgetExhaustedError:
            remaining = mem_budget.remaining()
            return (
                f"ERROR: Write budget exhausted "
                f"({mem_budget.writes_used}/{mem_budget.total_writes} used, "
                f"{remaining} remaining)."
            )
        entry_id = backend.add(content)
        remaining = mem_budget.remaining()
        return f"Stored (id={entry_id}). Budget: {remaining} writes remaining."

    @mcp.tool()
    def memory_search(query: str, top_k: int = 5) -> list[dict]:
        """Search stored memories by relevance. Free operation.

        Args:
            query: Search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of matching memories with id, content, and created_at.
        """
        return backend.search(query, top_k=top_k)

    @mcp.tool()
    def memory_update(memory_id: str, content: str) -> str:
        """Update an existing memory. Costs 1 write from your budget.

        Args:
            memory_id: The ID of the memory to update.
            content: The new content to replace the old content.

        Returns:
            Success or error message.
        """
        if len(content.split()) > mem_budget.max_content_tokens:
            return f"ERROR: Content exceeds {mem_budget.max_content_tokens} token limit."
        try:
            mem_budget.consume_write()
        except BudgetExhaustedError:
            return (
                f"ERROR: Write budget exhausted "
                f"({mem_budget.writes_used}/{mem_budget.total_writes} used)."
            )
        success = backend.update(memory_id, content)
        if not success:
            # Refund the write since update failed
            mem_budget.writes_used -= 1
            return f"ERROR: Memory {memory_id} not found."
        remaining = mem_budget.remaining()
        return f"Updated. Budget: {remaining} writes remaining."

    @mcp.tool()
    def memory_delete(memory_id: str) -> str:
        """Delete a memory. Free operation (does NOT refund write budget).

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            Success or error message.
        """
        success = backend.delete(memory_id)
        return "Deleted." if success else f"ERROR: Memory {memory_id} not found."

    @mcp.tool()
    def memory_list() -> list[dict]:
        """List all stored memories. Free operation.

        Returns:
            All memories sorted by creation time.
        """
        return backend.list_all()

    # Attach backend and budget for programmatic access
    mcp._memorybench_backend = backend
    mcp._memorybench_budget = mem_budget

    return mcp


def main():
    parser = argparse.ArgumentParser(description="MemoryBench MCP Server")
    parser.add_argument("--backend", default="mock",
                        choices=["mock", "chromadb"])
    parser.add_argument("--budget", type=int, default=30)
    args = parser.parse_args()

    server = create_server(backend_type=args.backend, budget=args.budget)
    server.run()


if __name__ == "__main__":
    main()
