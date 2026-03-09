"""ChromaDB memory backend: vector search with sentence-transformers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction,
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
        self._client = chromadb.Client()
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

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        # Primary: embedding similarity search
        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
        )
        entries = []
        seen_ids = set()
        for i in range(len(results["ids"][0])):
            eid = results["ids"][0][i]
            seen_ids.add(eid)
            entries.append({
                "id": eid,
                "content": results["documents"][0][i],
                "created_at": results["metadatas"][0][i].get("created_at", ""),
            })

        # Keyword fallback: substring match on all stored entries.
        # Embedding search can miss exact entity names when content
        # contains many attributes that dilute the entity name signal.
        query_lower = query.lower()
        if query_lower:
            all_results = self._collection.get()
            for i in range(len(all_results["ids"])):
                eid = all_results["ids"][i]
                if eid in seen_ids:
                    continue
                content = all_results["documents"][i]
                if query_lower in content.lower():
                    entries.append({
                        "id": eid,
                        "content": content,
                        "created_at": all_results["metadatas"][i].get(
                            "created_at", ""),
                    })
                    seen_ids.add(eid)

        return entries

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
        except Exception:
            return None

    def forget(self, memory_id: str) -> bool:
        try:
            existing = self._collection.get(ids=[memory_id])
            if not existing["ids"]:
                return False
            self._collection.delete(ids=[memory_id])
            return True
        except Exception:
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
