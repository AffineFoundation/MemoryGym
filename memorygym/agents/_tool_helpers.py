"""Tool execution and turn-analysis helpers for stream_agent.

Extracted from stream_agent.py to keep it under the 1000-line limit.
"""

from __future__ import annotations

from typing import Any

from memorygym.memory.budget import MemoryBudget

# Type alias: any backend implementing store/search/get/forget/list
MemoryBackend = Any


# -- Turn analysis helpers --------------------------------------------------

def budget_bar(used: int, total: int, width: int = 15) -> str:
    """Render a budget progress bar like [████░░░░░░] 6/15."""
    filled = round(used / total * width) if total else 0
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {used}/{total} writes"


def extract_stored_keys(turns: list[dict]) -> list[str]:
    """Extract entity names/keys from Write/memory_store calls in turn data."""
    keys = []
    for turn in turns:
        for call in turn.get("tool_calls", []):
            if call.get("name") in ("Write", "memory_store"):
                content = call.get("arguments", {}).get("content", "")
                # Common format: "EntityName | attr1: val1, ..."
                if "|" in content:
                    keys.append(content.split("|")[0].strip())
                elif content:
                    keys.append(content[:40])
    return keys


def extract_search_queries(turns: list[dict]) -> list[str]:
    """Extract search queries from memory_search calls."""
    queries = []
    for turn in turns:
        for call in turn.get("tool_calls", []):
            if call.get("name") == "memory_search":
                q = call.get("arguments", {}).get("query", "")
                if q:
                    queries.append(q)
    return queries


def extract_action_chain(turns: list[dict]) -> str:
    """Summarize tool call sequence as a chain like search→edit→answer."""
    actions = []
    for turn in turns:
        for call in turn.get("tool_calls", []):
            name = call.get("name", "")
            short = name.replace("memory_", "").replace("submit_", "").lower()
            if short and short not in actions[-1:]:
                actions.append(short)
    return " → ".join(actions) if actions else "(no action)"


def format_documents(docs: list[str]) -> str:
    """Format a list of documents with numbered headers."""
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[Document {i}]\n{doc}")
    return "\n\n".join(parts)


# -- Tool execution ---------------------------------------------------------

def execute_tool(
    name: str, args: dict, backend: MemoryBackend, budget: MemoryBudget,
) -> tuple[str, str | None]:
    """Execute a tool call. Returns (result_text, submitted_answer_or_None)."""
    if name == "submit_answer":
        return f"ANSWER_SUBMITTED: {args.get('answer', '')}", args.get("answer", "")

    # -- OpenClaw-compatible tools --
    if name == "Write" or name == "memory_store":
        content = args.get("content", "")
        if len(content) > 2000:
            return "Content exceeds 2000 character limit.", None
        if not budget.can_write():
            return f"Budget exhausted ({budget.writes_used}/{budget.total_writes}).", None
        budget.consume_write()
        if hasattr(backend, "write"):
            line_range = backend.write(content)
            return f"Written ({line_range}). {budget.remaining()} writes left.", None
        entry_id = backend.store(content)
        return f"Stored (id={entry_id}). {budget.remaining()} writes left.", None

    if name == "Edit":
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")
        if not old_text:
            return "old_text is required.", None
        if not budget.can_write():
            return f"Budget exhausted ({budget.writes_used}/{budget.total_writes}).", None
        budget.consume_write()
        if hasattr(backend, "edit"):
            ok = backend.edit(old_text, new_text)
            if not ok:
                budget.writes_used -= 1  # Refund on miss
                return "Text not found in memory.", None
            return f"Edited. {budget.remaining()} writes left.", None
        # Fallback for ChromaDB: search + forget + store
        results = backend.search(old_text, top_k=1)
        if results:
            backend.forget(results[0]["id"])
            content = results[0]["content"].replace(old_text, new_text, 1)
            backend.store(content)
            return f"Edited. {budget.remaining()} writes left.", None
        budget.writes_used -= 1  # Refund on miss
        return "Text not found in memory.", None

    if name == "Read" or name == "memory_get":
        if hasattr(backend, "read"):
            start = args.get("start_line")
            n = args.get("num_lines")
            content = backend.read(start_line=start, num_lines=n)
            if not content:
                return "Memory is empty.", None
            return content, None
        # Fallback: memory_get by ID
        mid = args.get("memory_id", "")
        if mid:
            entry = backend.get(mid)
            if not entry:
                return "Entry not found.", None
            return f"[{entry['id']}] {entry['content']}", None
        # List all
        entries = backend.list()
        if not entries:
            return "Memory is empty.", None
        lines = [f"[{e['id']}] {e['content']}" for e in entries]
        return "\n".join(lines), None

    if name == "memory_search":
        results = backend.search(args.get("query", ""), args.get("top_k", 5))
        if not results:
            return "No results found.", None
        lines = [f"[{r['id']}] {r['content']}" for r in results]
        return "\n".join(lines), None

    if name == "memory_forget":
        ok = backend.forget(args.get("memory_id", ""))
        return ("Deleted." if ok else "Entry not found."), None

    if name == "memory_list":
        entries = backend.list()
        if not entries:
            return "Memory is empty.", None
        lines = [f"[{e['id']}] {e['content']}" for e in entries]
        return "\n".join(lines), None

    return f"Unknown tool: {name}", None
