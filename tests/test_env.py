"""Tests for memorygym/env.py — Actor class (OpenEnv interface)."""

from __future__ import annotations

import asyncio

import pytest

from memorygym.env import Actor


def _run(coro):
    """Run async coroutine in sync test."""
    return asyncio.new_event_loop().run_until_complete(coro)


class TestParseTaskId:
    def test_seed_and_template_from_id(self):
        from memorygym.env import _parse_task_id
        from memorygym.worlds import ALL_TEMPLATES
        n = len(ALL_TEMPLATES)
        # task_id=0 → seed=0, first template
        seed, tmpl = _parse_task_id(0)
        assert seed == 0
        assert tmpl in ALL_TEMPLATES

    def test_roundtrip(self):
        from memorygym.env import _parse_task_id
        from memorygym.worlds import ALL_TEMPLATES
        templates = list(ALL_TEMPLATES.keys())
        n = len(templates)
        for i in range(n * 3):
            seed, tmpl = _parse_task_id(i)
            assert tmpl == templates[i % n]
            assert seed == i // n


class TestActorInit:
    def test_default_construction(self):
        actor = Actor()
        assert actor.api_key is None
        assert actor._episodes == {}

    def test_construction_with_api_key(self):
        actor = Actor(api_key="test-key")
        assert actor.api_key == "test-key"


class TestActorReset:
    def test_reset_returns_response(self):
        actor = Actor()
        resp = _run(actor.reset(seed=42))
        assert resp.done is False
        assert resp.reward == 0.0
        assert resp.episode_id is not None
        assert "seed" in resp.info

    def test_reset_creates_episode(self):
        actor = Actor()
        resp = _run(actor.reset(seed=0))
        assert resp.episode_id in actor._episodes


class TestActorStep:
    def test_step_unknown_episode(self):
        actor = Actor()
        resp = _run(actor.step("action", episode_id="nonexistent"))
        assert resp.done is True
        assert "Unknown" in resp.observation

    def test_step_after_reset(self):
        actor = Actor()
        resp = _run(actor.reset(seed=0))
        step_resp = _run(actor.step("action", episode_id=resp.episode_id))
        assert step_resp.done is True  # interactive mode not supported


class TestActorState:
    def test_state_unknown_episode(self):
        actor = Actor()
        resp = _run(actor.state(episode_id="nonexistent"))
        assert resp.done is True

    def test_state_after_reset(self):
        actor = Actor()
        resp = _run(actor.reset(seed=0))
        state_resp = _run(actor.state(episode_id=resp.episode_id))
        assert state_resp.done is False
        assert "ready" in state_resp.observation


class TestActorStop:
    def test_stop_cleans_up(self):
        actor = Actor()
        resp = _run(actor.reset(seed=0))
        eid = resp.episode_id
        result = _run(actor.stop(episode_id=eid))
        assert result["stopped"] is True
        assert eid not in actor._episodes


class TestActorEvaluate:
    def test_invalid_template_raises(self):
        actor = Actor()
        with pytest.raises(ValueError, match="Unknown template"):
            _run(actor.evaluate(
                model="test", base_url="http://fake",
                template="nonexistent"))

    def test_invalid_tier_raises(self):
        actor = Actor()
        with pytest.raises(ValueError, match="Unknown tier"):
            _run(actor.evaluate(
                model="test", base_url="http://fake",
                tier="impossible"))
