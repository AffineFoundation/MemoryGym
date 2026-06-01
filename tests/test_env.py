"""Tests for memorygym/env.py — Actor class (OpenEnv interface)."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from memorygym.env import Actor


def _run(coro):
    """Run async coroutine in sync test."""
    return asyncio.new_event_loop().run_until_complete(coro)


class TestParseTaskId:
    def test_all_ids_map_correctly(self):
        from memorygym.env import _parse_task_id
        from memorygym.worlds import TEMPLATE_REGISTRY
        for i, expected in enumerate(TEMPLATE_REGISTRY):
            assert _parse_task_id(i) == expected

    def test_out_of_range_raises(self):
        from memorygym.env import _parse_task_id
        with pytest.raises(ValueError):
            _parse_task_id(-1)

    def test_stability_contract(self):
        """First 10 entries must never change — this IS the contract."""
        from memorygym.worlds import TEMPLATE_REGISTRY
        expected = [
            "company", "research", "city", "hospital", "sport",
            "movie", "university", "codebase", "project", "agentteam",
        ]
        assert TEMPLATE_REGISTRY[:10] == expected

    def test_determinism_same_task_id(self):
        """Same task_id always returns same template."""
        from memorygym.env import _parse_task_id
        for tid in range(10):
            assert _parse_task_id(tid) == _parse_task_id(tid)

    def test_large_task_id_wraps_by_registry(self):
        from memorygym.env import _parse_task_id
        from memorygym.worlds import TEMPLATE_REGISTRY

        assert _parse_task_id(len(TEMPLATE_REGISTRY)) == TEMPLATE_REGISTRY[0]


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

    def test_affent_workspace_gets_unique_eval_subdir(self, tmp_path, monkeypatch):
        from memorygym.env import _run_evaluation
        from memorygym.protocol import TIERS

        seen: list[str] = []

        def fake_run_affent_agent(**kwargs):
            seen.append(kwargs["workspace"])
            return [], 0, [], None, []

        monkeypatch.setattr(
            "memorygym.agents.affent_agent.run_affent_agent",
            fake_run_affent_agent,
        )

        def run_once():
            _run_evaluation(
                model="test",
                base_url="http://fake/v1",
                api_key="key",
                seed=0,
                template_name="company",
                tier="lite",
                tier_cfg=TIERS["lite"],
                affent_workspace=str(tmp_path),
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: run_once(), range(4)))

        assert len(seen) == 4
        assert len(set(seen)) == 4
        assert all(str(tmp_path) in workspace for workspace in seen)

    def test_successful_result_has_no_top_level_error(self, monkeypatch):
        from memorygym.agents.stream_agent import AgentResult
        from memorygym.env import _run_evaluation
        from memorygym.protocol import TIERS

        def fake_run_stream_agent(**kwargs):
            return (
                [
                    AgentResult(
                        question="q",
                        answer="",
                        ground_truth="a",
                        competency="retrieval",
                        purpose="",
                        correct=False,
                        n_writes=0,
                        n_searches=0,
                    )
                ],
                0,
                [],
                None,
                [],
            )

        monkeypatch.setattr(
            "memorygym.env.run_stream_agent",
            fake_run_stream_agent,
        )

        result = _run_evaluation(
            model="test",
            base_url="http://fake/v1",
            api_key="key",
            seed=0,
            template_name="company",
            tier="lite",
            tier_cfg=TIERS["lite"],
            agent_runner="stream",
        )

        assert result["success"] is True
        assert "error" not in result

    def test_invalid_result_sets_top_level_error(self, monkeypatch):
        from memorygym.agents.stream_agent import AgentResult
        from memorygym.env import _run_evaluation
        from memorygym.protocol import TIERS

        def fake_run_stream_agent(**kwargs):
            return (
                [
                    AgentResult(
                        question="q",
                        answer="",
                        ground_truth="a",
                        competency="retrieval",
                        purpose="",
                        correct=False,
                        n_writes=0,
                        n_searches=0,
                        error="Request timed out.",
                    )
                ],
                0,
                [],
                "infra_failure: event 1 question: Request timed out.",
                [],
            )

        monkeypatch.setattr(
            "memorygym.env.run_stream_agent",
            fake_run_stream_agent,
        )

        result = _run_evaluation(
            model="test",
            base_url="http://fake/v1",
            api_key="key",
            seed=0,
            template_name="company",
            tier="lite",
            tier_cfg=TIERS["lite"],
            agent_runner="stream",
        )

        assert result["success"] is False
        assert result["error"].startswith("infra_failure")

    def test_affent_max_turns_is_not_error(self, tmp_path):
        import json

        from memorygym.agents.affent_agent import _parse_trace

        trace = tmp_path / "trace.jsonl"
        trace.write_text(json.dumps({
            "type": "turn.end",
            "data": {"reason": "max_turns"},
        }))

        turn = _parse_trace(trace)

        assert turn.error is None
        assert turn.stop_reason == "max_turns"

    def test_affent_returncode_2_max_turns_is_not_error(self, tmp_path, monkeypatch):
        import json
        from types import SimpleNamespace

        from memorygym.agents.affent_agent import _run_affent_turn

        def fake_run(cmd, **kwargs):
            trace_path = cmd[cmd.index("--trace") + 1]
            with open(trace_path, "w") as f:
                f.write(json.dumps({
                    "type": "turn.end",
                    "data": {"reason": "max_turns"},
                }))
            return SimpleNamespace(returncode=2, stdout="", stderr="")

        config = tmp_path / "config.json"
        config.write_text("{}")
        monkeypatch.setattr(
            "memorygym.agents.affent_agent.subprocess.run",
            fake_run,
        )

        turn = _run_affent_turn(
            affent_bin="/bin/affentctl",
            workspace=tmp_path,
            model="model",
            base_url="http://example/v1",
            api_key="key",
            config_path=config,
            session_id="s",
            prompt="hi",
            max_turns=1,
        )

        assert turn.error is None
        assert turn.stop_reason == "max_turns"
