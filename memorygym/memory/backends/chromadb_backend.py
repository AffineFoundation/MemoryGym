"""ChromaDB memory backend: vector search with sentence-transformers."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone

import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction,
)


# Process-wide singleton Chroma client.
#
# Why: chromadb.Client() shares an underlying System keyed on the identifier
# "ephemeral" across the process. The chromadb internal init is unsafe under
# concurrency:
#
#   1. SharedSystemClient._create_system_if_not_exists writes the new System
#      into a class-level dict BEFORE calling new_system.start(). RustBindingsAPI
#      (created via System.instance(ServerAPI)) only sets `self.bindings` inside
#      .start(); a concurrent caller that observes the dict entry before start()
#      runs gets a partial-state System whose ServerAPI.bindings is undefined,
#      surfacing as `'RustBindingsAPI' object has no attribute 'bindings'`.
#
#   2. If a previous Client() init failed mid-way the broken System remains
#      cached in `_identifier_to_system`. The next Client() takes the else-branch
#      and returns the broken System verbatim — the caller never gets a healthy
#      client even on retry.
#
#   3. KeyError('ephemeral') surfaces when one thread's _release_system pops
#      the entry while another thread reads it via the _system property.
#
# Defenses below:
#   - Singleton + threading lock serialise our calls to chromadb.Client() so
#     two backends in the same process don't enter chromadb init concurrently.
#   - On failure we clear chromadb's class-level cache so the next attempt
#     is not poisoned by the previous broken System.
#   - Retry up to 3 times with short backoff to ride out transient races
#     in chromadb's internal threading.

_client_lock = threading.Lock()
_shared_client: chromadb.api.ClientAPI | None = None


def _get_shared_client(max_retries: int = 3) -> chromadb.api.ClientAPI:
    """Return the process-wide chromadb client, retrying on chromadb-internal
    init races. Raises RuntimeError if all retries fail.
    """
    global _shared_client
    last_err: BaseException | None = None
    for attempt in range(max_retries):
        if _shared_client is not None:
            return _shared_client
        with _client_lock:
            if _shared_client is not None:
                return _shared_client
            try:
                # Reset chromadb's class-level cache so we never inherit a
                # broken System from a previously failed Client() call.
                from chromadb.api.shared_system_client import (
                    SharedSystemClient,
                )
                SharedSystemClient.clear_system_cache()
                _shared_client = chromadb.Client()
                return _shared_client
            except (AttributeError, KeyError, RuntimeError) as exc:
                last_err = exc
                _shared_client = None
                # Clear again so the next attempt is on a clean slate.
                try:
                    from chromadb.api.shared_system_client import (
                        SharedSystemClient as _SSC,
                    )
                    _SSC.clear_system_cache()
                except Exception:
                    pass
        # Sleep outside the lock so other waiters can also retry.
        if attempt < max_retries - 1:
            time.sleep(0.3 * (attempt + 1))
    raise RuntimeError(
        f"ChromaDB Client init failed after {max_retries} retries: "
        f"{type(last_err).__name__}: {last_err}"
    )


class ChromaDBBackend:
    """Production memory backend using ChromaDB + sentence-transformers.

    Uses all-MiniLM-L6-v2 for embedding (384-dim, fast, good quality).
    Search returns cosine-similarity top-k results.
    """

    def __init__(
        self,
        collection_name: str = "memorygym",
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self._ef = SentenceTransformerEmbeddingFunction(
            model_name=model_name,
        )
        self._client = _get_shared_client()
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._ef,
        )

    def store(self, content: str, memory_id: str | None = None) -> str:
        """Store or update a memory entry. Returns the entry ID."""
        if memory_id is not None:
            existing = self._collection.get(ids=[memory_id])
            if existing["ids"]:
                self._collection.update(
                    ids=[memory_id],
                    documents=[content],
                )
                return memory_id
            # ID not found — create new entry with this ID
            now = datetime.now(timezone.utc).isoformat()
            self._collection.add(
                ids=[memory_id],
                documents=[content],
                metadatas=[{"created_at": now}],
            )
            return memory_id
        entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._collection.add(
            ids=[entry_id],
            documents=[content],
            metadatas=[{"created_at": now}],
        )
        return entry_id

    @staticmethod
    def _entity_name(content: str) -> str:
        """Extract entity name prefix from stored content.

        Storage format: ``"EntityName | attr1: val1, attr2: val2"``.
        """
        sep = content.find(" | ")
        return (content[:sep].strip() if sep >= 0 else content.strip()).lower()

    @staticmethod
    def _match_priority(query_lower: str, content: str) -> int:
        """Score how well *content* matches *query_lower* (lower=better).

        0 = exact entity-name match
        1 = query is a sub-/super-string of the entity name
        2 = query appears somewhere in content (keyword hit)
        3 = embedding similarity only (no textual overlap)
        """
        entity = ChromaDBBackend._entity_name(content)
        if entity == query_lower:
            return 0
        if query_lower in entity or entity in query_lower:
            return 1
        if query_lower in content.lower():
            return 2
        return 3

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []

        query_lower = query.lower().strip()

        # Expand embedding search to gather more reranking candidates.
        expanded_k = min(top_k * 3, count)
        results = self._collection.query(
            query_texts=[query],
            n_results=expanded_k,
        )

        # (priority, original_rank, entry_dict)
        candidates: list[tuple[int, int, dict]] = []
        seen_ids: set[str] = set()

        for i in range(len(results["ids"][0])):
            eid = results["ids"][0][i]
            content = results["documents"][0][i]
            seen_ids.add(eid)
            priority = self._match_priority(query_lower, content)
            candidates.append((priority, i, {
                "id": eid,
                "content": content,
                "created_at": results["metadatas"][0][i].get(
                    "created_at", ""),
            }))

        # Keyword fallback: scan all entries for substring matches
        # missed by embedding search.
        if query_lower:
            all_results = self._collection.get()
            for i in range(len(all_results["ids"])):
                eid = all_results["ids"][i]
                if eid in seen_ids:
                    continue
                content = all_results["documents"][i]
                priority = self._match_priority(query_lower, content)
                if priority <= 2:  # has textual overlap
                    seen_ids.add(eid)
                    candidates.append((priority, expanded_k + i, {
                        "id": eid,
                        "content": content,
                        "created_at": all_results["metadatas"][i].get(
                            "created_at", ""),
                    }))

        # Rerank: entity-name matches first, then embedding rank.
        candidates.sort(key=lambda c: (c[0], c[1]))
        return [c[2] for c in candidates[:top_k]]

    def get(self, memory_id: str) -> dict | None:
        """Retrieve a single entry by ID."""
        try:
            results = self._collection.get(ids=[memory_id])
            if not results["ids"]:
                return None
            return {
                "id": results["ids"][0],
                "content": results["documents"][0],
                "created_at": results["metadatas"][0].get("created_at", ""),
            }
        except (ValueError, KeyError, IndexError):
            return None

    def forget(self, memory_id: str) -> bool:
        try:
            existing = self._collection.get(ids=[memory_id])
            if not existing["ids"]:
                return False
            self._collection.delete(ids=[memory_id])
            return True
        except (ValueError, KeyError):
            return False

    def list(self) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.get()
        entries = []
        for i in range(len(results["ids"])):
            entries.append({
                "id": results["ids"][i],
                "content": results["documents"][i],
                "created_at": results["metadatas"][i].get("created_at", ""),
            })
        return entries

    def clear(self) -> None:
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection.name,
            embedding_function=self._ef,
        )

    def close(self) -> None:
        """Delete the collection and release client references.

        Idempotent: safe to call multiple times.
        """
        if self._client is None:
            return
        try:
            self._client.delete_collection(self._collection.name)
        except Exception:
            pass
        self._client = None
        self._collection = None
