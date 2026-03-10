"""Real mem0 backend using the mem0ai Python SDK.

Requires: pip install mem0ai

mem0 uses an LLM to automatically extract and consolidate facts from
raw text. This means a single store() call may create multiple memory
entries (one per extracted fact). This is fundamentally different from
ChromaDB which stores content verbatim.
"""

from __future__ import annotations

import os
from typing import Any

from mem0 import Memory

from memorygym.config import get_api_config


def _default_config() -> dict[str, Any]:
    """Build mem0 config from global API configuration."""
    cfg = get_api_config()
    model = os.environ.get(
        "MEM0_LLM_MODEL", "Qwen/Qwen3-235B-A22B-Instruct-2507-TEE")

    config: dict[str, Any] = {
        "llm": {"provider": "openai", "config": {
            "model": model,
            "api_key": cfg.api_key,
            "openai_base_url": cfg.api_url,
        }},
        "embedder": {"provider": "huggingface", "config": {
            "model": "all-MiniLM-L6-v2",
        }},
        "vector_store": {"provider": "qdrant", "config": {
            "collection_name": "memorygym",
            "path": "/tmp/mem0_qdrant",
            "embedding_model_dims": 384,
        }},
    }
    return config


class Mem0Backend:
    """Production backend using mem0 (https://github.com/mem0ai/mem0).

    Delegates all operations to the mem0 SDK, mapping the MemoryGym
    backend interface to mem0's API.

    When no config is provided, uses global API config (memorygym.config).

    Args:
        config: mem0 config dict. If None, uses global API config.
        user_id: mem0 user ID for scoping memories.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        user_id: str = "memorygym",
    ) -> None:
        if config is None:
            config = _default_config()
        self._m = Memory.from_config(config)
        self._user_id = user_id

    def store(self, content: str, memory_id: str | None = None) -> str:
        """Store or update a memory entry. Returns the entry ID.

        Note: mem0 uses LLM to extract facts. A single store() may
        create multiple entries. Returns the first entry's ID.
        """
        if memory_id is not None:
            self._m.update(memory_id, content)
            return memory_id
        result = self._m.add(content, user_id=self._user_id)
        # mem0 v1.0+ returns {"results": [{"id": ..., "memory": ...}, ...]}
        entries = result.get("results", [])
        if not entries:
            raise RuntimeError(
                f"mem0 extracted no facts from content ({len(content)} chars)")
        return entries[0]["id"]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        result = self._m.search(query, user_id=self._user_id, limit=top_k)
        # mem0 v1.0+ returns {"results": [...]}
        entries = result.get("results", []) if isinstance(result, dict) else result
        return [
            {
                "id": r["id"],
                "content": r.get("memory", ""),
                "created_at": r.get("created_at", ""),
            }
            for r in entries
        ]

    def get(self, memory_id: str) -> dict | None:
        """Retrieve a single entry by ID."""
        try:
            r = self._m.get(memory_id)
        except (ValueError, KeyError):
            return None
        if not r:
            return None
        return {
            "id": r["id"],
            "content": r.get("memory", ""),
            "created_at": r.get("created_at", ""),
        }

    def forget(self, memory_id: str) -> bool:
        try:
            self._m.delete(memory_id)
            return True
        except (ValueError, KeyError):
            return False

    def list(self) -> list[dict]:
        result = self._m.get_all(user_id=self._user_id)
        entries = result.get("results", []) if isinstance(result, dict) else result
        return [
            {
                "id": r["id"],
                "content": r.get("memory", ""),
                "created_at": r.get("created_at", ""),
            }
            for r in entries
        ]

    def clear(self) -> None:
        self._m.delete_all(user_id=self._user_id)
