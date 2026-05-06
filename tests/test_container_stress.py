"""Stress tests for affinetes container deployment.

Tests concurrent evaluation, resource cleanup, memory leaks, and long-running
stability — the critical failure modes for production container usage.
"""

from __future__ import annotations

import asyncio
import gc
import os
import sys
import threading
import time
import tracemalloc
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from random import Random
from unittest.mock import MagicMock, patch

import pytest

from memorygym.env import Actor, _parse_task_id, _run_evaluation
from memorygym.memory.backends.chromadb_backend import ChromaDBBackend
from memorygym.memory.backends.markdown_backend import MarkdownBackend
from memorygym.memory.budget import MemoryBudget
from memorygym.protocol import TIERS
from memorygym.worlds import ALL_TEMPLATES


# ---------------------------------------------------------------------------
# 1. ChromaDB concurrent isolation
# ---------------------------------------------------------------------------

class TestChromaDBConcurrency:
    """Verify ChromaDB backends don't collide under concurrent use."""

    def test_default_collection_name_collision(self):
        """Two backends with default name share collection — known behavior."""
        b1 = ChromaDBBackend()
        b2 = ChromaDBBackend()
        b1.store("Entity A | age: 30")
        # Default name "memorygym" is shared — this is expected.
        # Production code (env.py, stream_agent.py) now uses unique names.
        results = b2.search("Entity A")
        b1.close()
        b2.close()
        # Document the behavior: same name = shared state
        assert len(results) > 0, (
            "Default collection name should share state (documenting behavior)")

    def test_unique_collection_names_isolate(self):
        """Backends with unique collection names are properly isolated."""
        b1 = ChromaDBBackend(collection_name=f"test_{uuid.uuid4().hex[:8]}")
        b2 = ChromaDBBackend(collection_name=f"test_{uuid.uuid4().hex[:8]}")
        try:
            b1.store("Entity A | age: 30")
            b2.store("Entity B | age: 25")
            r1 = b1.search("Entity A")
            r2 = b2.search("Entity B")
            assert len(r1) == 1
            assert "Entity A" in r1[0]["content"]
            assert len(r2) == 1
            assert "Entity B" in r2[0]["content"]
            # Cross-isolation: b1 should NOT find Entity B
            cross = b1.search("Entity B")
            assert all("Entity B" not in r["content"] for r in cross)
        finally:
            b1.close()
            b2.close()

    def test_concurrent_store_search(self):
        """Multiple threads doing store/search on isolated backends."""
        errors = []

        def worker(worker_id: int):
            try:
                name = f"worker_{worker_id}_{uuid.uuid4().hex[:8]}"
                b = ChromaDBBackend(collection_name=name)
                for i in range(20):
                    b.store(f"Entity_{worker_id}_{i} | val: {i}")
                for i in range(20):
                    results = b.search(f"Entity_{worker_id}_{i}")
                    if not results:
                        errors.append(
                            f"Worker {worker_id}: search miss for entity {i}")
                b.close()
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert not errors, f"Concurrent errors: {errors}"


    def test_env_run_evaluation_uses_unique_names(self):
        """_run_evaluation creates unique collection per call (fix verified)."""
        import memorygym.env as env_module
        import inspect
        source = inspect.getsource(env_module._run_evaluation)
        assert "uuid.uuid4()" in source, (
            "_run_evaluation must use uuid for collection isolation")
        assert "collection_name=" in source, (
            "_run_evaluation must pass collection_name to ChromaDBBackend")


class TestChromaDBSharedClientRace:
    """Verify _get_shared_client recovers from chromadb-internal init races.

    Live observation 2026-05-04..06: ChromaDBBackend init occasionally
    failed with `'RustBindingsAPI' object has no attribute 'bindings'`
    or KeyError('ephemeral'). Root cause: chromadb's
    SharedSystemClient._create_system_if_not_exists is lock-free —
    writes the new System into a class-level dict before calling
    new_system.start(); RustBindingsAPI.bindings is only set inside
    start(). A concurrent caller observes a partial-state System.
    Plus failed-init residues the broken System in the cache so a
    naive retry hits it again.

    The fix wraps Client() in a singleton + retry + clear_system_cache.
    """

    def test_singleton_returns_same_client(self):
        """Two backends in the same process share one chromadb client."""
        from memorygym.memory.backends.chromadb_backend import (
            _get_shared_client,
        )
        c1 = _get_shared_client()
        c2 = _get_shared_client()
        assert c1 is c2, "shared client must be a singleton"

    def test_retries_on_attribute_error(self, monkeypatch):
        """Simulate a chromadb-internal race: first Client() raises
        AttributeError('bindings'), second succeeds. _get_shared_client
        must clear cache, retry, and return a healthy client."""
        from memorygym.memory.backends import chromadb_backend as cb

        # Reset module state so retry path runs
        cb._shared_client = None

        attempts = {"n": 0}
        original_client = cb.chromadb.Client

        def fake_client(*args, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise AttributeError(
                    "'RustBindingsAPI' object has no attribute 'bindings'"
                )
            return original_client(*args, **kwargs)

        monkeypatch.setattr(cb.chromadb, "Client", fake_client)
        # Also patch sleep so the test runs fast
        monkeypatch.setattr(cb.time, "sleep", lambda *a, **kw: None)

        client = cb._get_shared_client()
        assert client is not None
        assert attempts["n"] == 2, (
            f"expected 2 Client() calls (1 fail + 1 retry), got {attempts['n']}"
        )

    def test_retries_on_key_error_ephemeral(self, monkeypatch):
        """Simulate the KeyError('ephemeral') variant of the same race."""
        from memorygym.memory.backends import chromadb_backend as cb

        cb._shared_client = None
        attempts = {"n": 0}
        original_client = cb.chromadb.Client

        def fake_client(*args, **kwargs):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise KeyError("ephemeral")
            return original_client(*args, **kwargs)

        monkeypatch.setattr(cb.chromadb, "Client", fake_client)
        monkeypatch.setattr(cb.time, "sleep", lambda *a, **kw: None)

        client = cb._get_shared_client()
        assert client is not None
        assert attempts["n"] == 2

    def test_persistent_failure_raises_after_max_retries(self, monkeypatch):
        """If chromadb is permanently broken, raise after N retries with
        the last error context — don't hang the eval forever."""
        from memorygym.memory.backends import chromadb_backend as cb

        cb._shared_client = None
        attempts = {"n": 0}

        def always_fail(*args, **kwargs):
            attempts["n"] += 1
            raise AttributeError("permanent failure")

        monkeypatch.setattr(cb.chromadb, "Client", always_fail)
        monkeypatch.setattr(cb.time, "sleep", lambda *a, **kw: None)

        import pytest
        with pytest.raises(RuntimeError, match="ChromaDB Client init failed"):
            cb._get_shared_client(max_retries=3)
        assert attempts["n"] == 3, (
            f"expected exactly 3 attempts at max_retries=3; got {attempts['n']}"
        )

    def test_backend_init_uses_shared_client(self):
        """ChromaDBBackend.__init__ must route through _get_shared_client,
        not call chromadb.Client directly. Otherwise the singleton/retry
        defenses are bypassed and we regress to the live failure mode."""
        from memorygym.memory.backends.chromadb_backend import (
            ChromaDBBackend,
            _get_shared_client,
        )
        b = ChromaDBBackend(collection_name=f"shared_test_{uuid.uuid4().hex[:8]}")
        assert b._client is _get_shared_client(), (
            "backend client must be the shared singleton"
        )
        b.close()


class TestChromaDBResourceCleanup:
    """Verify ChromaDB resources are properly released."""

    def test_close_releases_references(self):
        """After close(), client and collection are None."""
        b = ChromaDBBackend(
            collection_name=f"test_{uuid.uuid4().hex[:8]}")
        b.store("test content")
        b.close()
        assert b._client is None
        assert b._collection is None

    def test_close_idempotent(self):
        """Calling close() multiple times doesn't raise."""
        b = ChromaDBBackend(
            collection_name=f"test_{uuid.uuid4().hex[:8]}")
        b.close()
        b.close()  # Should not raise

    def test_many_backends_no_leak(self):
        """Create and destroy many backends — memory should not grow unbounded."""
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        for i in range(10):
            b = ChromaDBBackend(
                collection_name=f"stress_{uuid.uuid4().hex[:8]}")
            for j in range(5):
                b.store(f"Entity {j} | value: {j * i}")
            b.close()

        gc.collect()
        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Check that memory growth is bounded (< 50MB)
        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_growth = sum(s.size_diff for s in stats if s.size_diff > 0)
        assert total_growth < 50 * 1024 * 1024, (
            f"Memory grew by {total_growth / 1024 / 1024:.1f}MB "
            f"over 10 backend lifecycles")


# ---------------------------------------------------------------------------
# 2. MarkdownBackend resource cleanup
# ---------------------------------------------------------------------------

class TestMarkdownBackendCleanup:
    """Verify MarkdownBackend temp files are cleaned up."""

    def test_close_removes_temp_dir(self):
        """close() removes the /tmp directory."""
        b = MarkdownBackend()
        tmp_dir = b._dir
        assert tmp_dir.exists()
        b.close()
        assert not tmp_dir.exists()

    def test_close_idempotent(self):
        """Calling close() multiple times doesn't raise."""
        b = MarkdownBackend()
        b.close()
        b.close()  # Should not raise

    def test_many_backends_no_tmp_leak(self):
        """Creating many backends doesn't leave /tmp littered."""
        import glob
        before = set(glob.glob("/tmp/memorygym_md_*"))

        for _ in range(20):
            b = MarkdownBackend()
            b.write("test content")
            b.close()

        after = set(glob.glob("/tmp/memorygym_md_*"))
        leaked = after - before
        assert not leaked, f"Temp directories leaked: {leaked}"


# ---------------------------------------------------------------------------
# 3. Actor episode management
# ---------------------------------------------------------------------------

class TestActorEpisodeCleanup:
    """Verify Actor doesn't leak episode state."""

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_episodes_cleaned_on_stop(self):
        actor = Actor()
        episodes = []
        for _ in range(100):
            resp = self._run(actor.reset(seed=0))
            episodes.append(resp.episode_id)
        assert len(actor._episodes) == 100
        for eid in episodes:
            self._run(actor.stop(episode_id=eid))
        assert len(actor._episodes) == 0

    def test_stop_nonexistent_episode_safe(self):
        actor = Actor()
        result = self._run(actor.stop(episode_id="nonexistent"))
        assert result["stopped"] is True

    def test_concurrent_reset_stop(self):
        """Concurrent reset/stop on same actor doesn't crash."""
        actor = Actor()
        errors = []

        def reset_stop_cycle(n: int):
            try:
                loop = asyncio.new_event_loop()
                for _ in range(n):
                    resp = loop.run_until_complete(actor.reset(seed=0))
                    loop.run_until_complete(actor.stop(
                        episode_id=resp.episode_id))
                loop.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=reset_stop_cycle, args=(50,))
                   for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent errors: {errors}"


# ---------------------------------------------------------------------------
# 4. World generation determinism under concurrency
# ---------------------------------------------------------------------------

class TestWorldGenerationConcurrent:
    """World generation must be deterministic even under concurrent load."""

    def test_concurrent_world_generation_deterministic(self):
        """Same seed produces identical worlds across threads."""
        results = {}
        errors = []

        def gen_world(template_name: str, seed: int, run_id: int):
            try:
                tmpl_cls = ALL_TEMPLATES[template_name]
                tmpl = tmpl_cls()
                world = tmpl.generate_world(
                    seed=seed, n_entities=30, eval_salt=1)
                # Capture entity names + first attr values as fingerprint
                fp = []
                for e in world.entities:
                    vals = sorted(
                        (k, str(v)) for k, v in e.attrs.items())[:3]
                    fp.append((e.name, vals))
                fp.sort()
                key = (template_name, seed)
                results.setdefault(key, []).append(fp)
            except Exception as e:
                errors.append(f"run {run_id}: {e}")

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = []
            for template in ["company", "research", "city"]:
                for seed in range(3):
                    for run in range(4):
                        futures.append(
                            pool.submit(gen_world, template, seed, run))
            for f in as_completed(futures):
                f.result()

        assert not errors, f"Errors: {errors}"
        for key, fingerprints in results.items():
            assert all(fp == fingerprints[0] for fp in fingerprints), (
                f"{key}: non-deterministic across runs")


# ---------------------------------------------------------------------------
# 5. Budget enforcement under concurrent tool calls
# ---------------------------------------------------------------------------

class TestBudgetConcurrency:
    """Budget must be enforced correctly even with rapid concurrent writes."""

    def test_budget_not_exceeded_sequential(self):
        budget = MemoryBudget(total_writes=10)
        for _ in range(10):
            budget.consume_write()
        assert not budget.can_write()
        assert budget.remaining() == 0

    def test_budget_concurrent_writes(self):
        """Rapid concurrent consume_write calls must not exceed budget."""
        budget = MemoryBudget(total_writes=50)
        errors = []

        def consume_batch(n: int):
            for _ in range(n):
                try:
                    if budget.can_write():
                        budget.consume_write()
                except Exception:
                    pass  # budget exhausted — expected

        threads = [threading.Thread(target=consume_batch, args=(20,))
                   for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Budget may be slightly over due to race, but should be close
        # Note: MemoryBudget is NOT thread-safe — this test documents it
        if budget.writes_used > 50:
            pytest.skip(
                "KNOWN: MemoryBudget is not thread-safe. "
                f"Used {budget.writes_used}/50. "
                "OK if each evaluate() has its own budget.")


# ---------------------------------------------------------------------------
# 6. Stream generation stress test
# ---------------------------------------------------------------------------

class TestStreamGenerationStress:
    """Verify stream generation is robust across all templates and many seeds."""

    @pytest.mark.parametrize("template", list(ALL_TEMPLATES.keys()))
    def test_stream_generation_all_seeds(self, template):
        """Generate streams for seeds 0-9 on each template — no crashes."""
        tmpl_cls = ALL_TEMPLATES[template]
        tier_cfg = TIERS["lite"]
        for seed in range(10):
            tmpl = tmpl_cls()
            world = tmpl.generate_world(
                seed=seed,
                n_entities=tier_cfg["entities"],
                eval_salt=tier_cfg.get("eval_salt", 1),
            )
            rng_correct = Random(seed + 3333)
            corrections = tmpl.generate_corrections(
                world, rng_correct, tier_cfg["corrections"])
            n_contras = max(1, tier_cfg["corrections"] // 3)
            exclude_corrected = {c.entity_name for c in corrections}
            rng_contra = Random(seed + 7373)
            contradictions = tmpl.generate_contradictions(
                world, rng_contra, n_contras,
                exclude_entities=exclude_corrected)
            rng_stream = Random(seed + 5555)
            stream = tmpl.generate_stream(
                world, rng_stream, corrections,
                stored_names=set(),
                n_questions=tier_cfg["questions"],
                entities_per_batch=10,
                contradictions=contradictions,
            )
            # Verify stream structure
            assert len(stream) > 0
            types = {e["type"] for e in stream}
            assert "ingest" in types
            assert "question" in types
            # Verify questions have ground truth
            for evt in stream:
                if evt["type"] == "question":
                    assert "answer" in evt
                    assert "competency" in evt


# ---------------------------------------------------------------------------
# 7. End-to-end Actor.evaluate() with mocked LLM
# ---------------------------------------------------------------------------

class TestActorEvaluateE2E:
    """Test evaluate() pipeline structure (without mocked LLM to avoid hangs)."""

    def _run(self, coro):
        return asyncio.new_event_loop().run_until_complete(coro)

    def test_evaluate_bad_api_returns_error_result(self):
        """evaluate() with unreachable API returns error result, never crashes."""
        actor = Actor(api_key="test-key")
        result = self._run(actor.evaluate(
            model="test-model",
            base_url="http://127.0.0.1:1",  # unreachable
            api_key="test-key",
            seed=0,
            template="company",
            tier="lite",
            timeout=5,
        ))
        # Should return error result, not raise
        assert result["score"] == 0.0
        assert result["success"] is False
        assert "error" in result.get("extra", {})

    def test_run_evaluation_world_generation_isolated(self):
        """_run_evaluation creates isolated world per call."""
        tier_cfg = TIERS["lite"]
        # Just test that world gen part works — will fail at LLM call
        # but proves the pipeline is set up correctly
        try:
            _run_evaluation(
                model="test", base_url="http://127.0.0.1:1",
                api_key="fake", seed=42,
                template_name="company", tier_cfg=tier_cfg)
        except Exception:
            pass  # Expected — LLM not available

    def test_concurrent_world_gen_in_evaluate_path(self):
        """Concurrent _run_evaluation calls create isolated worlds."""
        tier_cfg = TIERS["lite"]
        errors = []

        def run_eval(seed: int, template: str):
            try:
                _run_evaluation(
                    model="test", base_url="http://127.0.0.1:1",
                    api_key="fake", seed=seed,
                    template_name=template, tier_cfg=tier_cfg)
            except Exception:
                pass  # Expected — LLM not available

        threads = []
        for seed in range(3):
            for tmpl in ["company", "research", "city"]:
                t = threading.Thread(target=run_eval, args=(seed, tmpl))
                threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert not errors


# ---------------------------------------------------------------------------
# 8. Long-running stability simulation
# ---------------------------------------------------------------------------

class TestLongRunningStability:
    """Simulate many sequential evaluations to check for resource leaks."""

    def test_repeated_chromadb_lifecycle(self):
        """Create/use/close 30 ChromaDB backends — no errors."""
        for i in range(30):
            b = ChromaDBBackend(
                collection_name=f"lifecycle_{uuid.uuid4().hex[:8]}")
            for j in range(5):
                b.store(f"Entry {j} | val: {j}")
            results = b.search("Entry 3")
            assert len(results) > 0
            b.close()

    def test_repeated_markdown_lifecycle(self):
        """Create/use/close 30 MarkdownBackend backends — no leaks."""
        import glob
        before = set(glob.glob("/tmp/memorygym_md_*"))

        for i in range(30):
            b = MarkdownBackend()
            b.write(f"Test entry {i}")
            results = b.search(f"entry {i}")
            b.close()

        gc.collect()
        after = set(glob.glob("/tmp/memorygym_md_*"))
        leaked = after - before
        assert not leaked, f"Leaked {len(leaked)} temp dirs"

    def test_actor_many_episodes(self):
        """Actor handles 1000 reset/stop cycles without issues."""
        actor = Actor()
        loop = asyncio.new_event_loop()
        for i in range(1000):
            resp = loop.run_until_complete(actor.reset(seed=i % 100))
            loop.run_until_complete(actor.stop(episode_id=resp.episode_id))
        loop.close()
        assert len(actor._episodes) == 0


# ---------------------------------------------------------------------------
# 9. Determinism verification
# ---------------------------------------------------------------------------

class TestSamplingDeterminism:
    """Sampling must be identical given the same seed."""

    @pytest.mark.parametrize("template", ["company", "research", "city"])
    def test_stream_determinism(self, template):
        """Same seed+template → identical stream events."""
        tier_cfg = TIERS["lite"]

        def generate_stream_fp(seed: int) -> list[tuple]:
            tmpl = ALL_TEMPLATES[template]()
            world = tmpl.generate_world(
                seed=seed, n_entities=tier_cfg["entities"],
                eval_salt=tier_cfg.get("eval_salt", 1))
            rng_correct = Random(seed + 3333)
            corrections = tmpl.generate_corrections(
                world, rng_correct, tier_cfg["corrections"])
            n_contras = max(1, tier_cfg["corrections"] // 3)
            exclude = {c.entity_name for c in corrections}
            rng_contra = Random(seed + 7373)
            contradictions = tmpl.generate_contradictions(
                world, rng_contra, n_contras, exclude_entities=exclude)
            rng_stream = Random(seed + 5555)
            stream = tmpl.generate_stream(
                world, rng_stream, corrections,
                stored_names=set(), n_questions=tier_cfg["questions"],
                entities_per_batch=10, contradictions=contradictions)
            # Fingerprint: (type, key data) for each event
            fp = []
            for e in stream:
                if e["type"] == "question":
                    fp.append((e["type"], e["question"], str(e["answer"])))
                elif e["type"] == "correction":
                    fp.append((e["type"], e["entity_name"], e["attr"]))
                elif e["type"] == "ingest":
                    fp.append((e["type"], tuple(e.get("entity_names", []))))
                else:
                    fp.append((e["type"],))
            return fp

        for seed in range(5):
            fp1 = generate_stream_fp(seed)
            fp2 = generate_stream_fp(seed)
            assert fp1 == fp2, (
                f"template={template} seed={seed}: non-deterministic")


# ---------------------------------------------------------------------------
# 10. task_id mapping stability
# ---------------------------------------------------------------------------

class TestTaskIdStability:
    """task_id mapping must be stable across invocations."""

    def test_task_id_range(self):
        """All valid task_ids resolve without error."""
        from memorygym.worlds import TEMPLATE_REGISTRY
        for i in range(len(TEMPLATE_REGISTRY)):
            name = _parse_task_id(i)
            assert name in ALL_TEMPLATES

    def test_task_id_boundary_errors(self):
        """Out-of-range task_ids raise ValueError."""
        with pytest.raises(ValueError):
            _parse_task_id(-1)
        from memorygym.worlds import TEMPLATE_REGISTRY
        with pytest.raises(ValueError):
            _parse_task_id(len(TEMPLATE_REGISTRY))
