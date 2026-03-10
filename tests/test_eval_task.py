"""Tests for memorygym/worlds/eval_task.py — Inspect AI task."""

from __future__ import annotations

import pytest

from memorygym.protocol import TIERS


class TestWorldbenchTierParam:
    def test_tier_lite_sets_defaults(self):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(seed=0, template="company", tier="lite")
        meta = task.dataset.samples[0].metadata
        tc = TIERS["lite"]
        assert meta["n_entities"] == tc["entities"]
        assert meta["n_questions"] == tc["questions"]
        assert meta["n_corrections"] == tc["corrections"]
        assert meta["write_budget"] == tc["write_budget"]

    def test_tier_standard(self):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(seed=0, template="company", tier="standard")
        meta = task.dataset.samples[0].metadata
        tc = TIERS["standard"]
        assert meta["n_entities"] == tc["entities"]
        assert meta["n_questions"] == tc["questions"]

    def test_tier_hard(self):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(seed=0, template="company", tier="hard")
        meta = task.dataset.samples[0].metadata
        tc = TIERS["hard"]
        assert meta["n_entities"] == tc["entities"]

    def test_tier_multi(self):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(seed=0, template="company", tier="multi")
        meta = task.dataset.samples[0].metadata
        tc = TIERS["multi"]
        assert meta["n_entities"] == tc["entities"]
        assert meta["n_questions"] == tc["questions"]

    def test_explicit_params_override_tier(self):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(
            seed=0, template="company", tier="lite",
            n_entities=100)
        meta = task.dataset.samples[0].metadata
        assert meta["n_entities"] == 100  # overridden
        assert meta["n_questions"] == TIERS["lite"]["questions"]  # from tier

    def test_invalid_tier_raises(self):
        from memorygym.worlds.eval_task import worldbench
        with pytest.raises(ValueError, match="Unknown tier"):
            worldbench(seed=0, tier="impossible")

    def test_no_tier_uses_defaults(self):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(seed=0, template="company")
        meta = task.dataset.samples[0].metadata
        assert meta["n_entities"] == 200  # original default

    def test_seed_required(self):
        from memorygym.worlds.eval_task import worldbench
        with pytest.raises(ValueError, match="seed is required"):
            worldbench()


class TestWorldbenchAllTemplates:
    @pytest.mark.parametrize("template", [
        "company", "research", "city", "hospital", "sport", "movie"])
    def test_template_creates_task(self, template):
        from memorygym.worlds.eval_task import worldbench
        task = worldbench(seed=0, template=template, tier="lite")
        assert task is not None
        assert task.name.startswith("worldbench_")

    def test_invalid_template_raises(self):
        from memorygym.worlds.eval_task import worldbench
        with pytest.raises(ValueError, match="Unknown template"):
            worldbench(seed=0, template="nonexistent")


class TestBuildWorldbenchStream:
    def test_stream_has_events(self):
        from memorygym.worlds.eval_task import build_worldbench_stream
        data = build_worldbench_stream(seed=0, template_name="company",
                                       n_entities=10, n_questions=5)
        assert "stream" in data
        assert len(data["stream"]) > 0
        assert data["seed"] == 0
        assert data["template_name"] == "company"

    def test_deterministic(self):
        from memorygym.worlds.eval_task import build_worldbench_stream
        d1 = build_worldbench_stream(seed=42, template_name="company",
                                      n_entities=10, n_questions=5)
        d2 = build_worldbench_stream(seed=42, template_name="company",
                                      n_entities=10, n_questions=5)
        assert len(d1["stream"]) == len(d2["stream"])
