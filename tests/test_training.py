"""Tests for training data interfaces."""

from __future__ import annotations

import json
from pathlib import Path

from memorygym.training import (
    MemoryEnv,
    export_trajectories,
    generate_sft_trajectory,
)


class TestSFTTrajectory:
    """SFT trajectory generation."""

    def test_generates_valid_messages(self):
        messages = generate_sft_trajectory("company", seed=0)
        assert isinstance(messages, list)
        assert len(messages) > 0
        # First message is system
        assert messages[0]["role"] == "system"
        # All messages have role and content
        for msg in messages:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("system", "user", "assistant")

    def test_contains_tool_calls(self):
        messages = generate_sft_trajectory("company", seed=0)
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) > 0
        # At least some should contain tool_call tags or tool names
        has_tools = any(
            "tool_call" in m["content"] or "memory_store" in m["content"]
            for m in assistant_msgs
        )
        assert has_tools

    def test_contains_submit_answer(self):
        messages = generate_sft_trajectory("company", seed=0)
        has_submit = any(
            "submit_answer" in m["content"]
            for m in messages if m["role"] == "assistant"
        )
        assert has_submit

    def test_strategic_stores_fewer(self):
        perfect = generate_sft_trajectory("company", seed=0, strategy="perfect")
        strategic = generate_sft_trajectory("company", seed=0, strategy="strategic")
        # Perfect should have more store calls
        perfect_stores = sum(
            m["content"].count("memory_store")
            for m in perfect if m["role"] == "assistant"
        )
        strategic_stores = sum(
            m["content"].count("memory_store")
            for m in strategic if m["role"] == "assistant"
        )
        assert perfect_stores > strategic_stores

    def test_all_templates(self):
        for tname in ("company", "research", "city", "hospital", "sport"):
            messages = generate_sft_trajectory(tname, seed=0)
            assert len(messages) > 0

    def test_messages_are_json_serializable(self):
        messages = generate_sft_trajectory("company", seed=0)
        # Should not raise
        json.dumps(messages)


class TestExportTrajectories:
    """Batch trajectory export."""

    def test_creates_jsonl_files(self, tmp_path):
        files = export_trajectories(
            n_seeds=2, strategy="perfect",
            output_dir=str(tmp_path), templates=["company"])
        assert len(files) == 1
        assert files[0].exists()
        # Each line should be valid JSON with "messages" key
        lines = files[0].read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "messages" in data
            assert isinstance(data["messages"], list)


class TestMemoryEnv:
    """RL environment interface."""

    def test_reset_returns_text(self):
        env = MemoryEnv("company", seed=0)
        obs = env.reset()
        assert isinstance(obs, str)
        assert "DOCUMENTS" in obs or "Event" in obs

    def test_step_returns_text_observation(self):
        env = MemoryEnv("company", seed=0)
        env.reset()
        obs, reward, done, info = env.step({"tool": "next"})
        assert isinstance(obs, str)

    def test_step_store_and_search(self):
        env = MemoryEnv("company", seed=0)
        env.reset()
        # Store something
        obs, reward, done, info = env.step({
            "tool": "memory_store",
            "args": {"content": "Test entity | revenue: 1000"}
        })
        assert "memory_id" in info
        assert info["remaining"] == env.write_budget - 1

        # Search for it
        obs, reward, done, info = env.step({
            "tool": "memory_search",
            "args": {"query": "test entity"}
        })
        assert len(info["results"]) == 1

    def test_budget_exhaustion(self):
        env = MemoryEnv("company", seed=0, write_budget=2)
        env.reset()
        env.step({"tool": "memory_store", "args": {"content": "a"}})
        env.step({"tool": "memory_store", "args": {"content": "b"}})
        _, _, _, info = env.step({
            "tool": "memory_store", "args": {"content": "c"}})
        assert "error" in info

    def test_full_episode(self):
        env = MemoryEnv("company", seed=0, n_entities=10, n_questions=5)
        obs = env.reset()
        assert isinstance(obs, str)
        done = False
        steps = 0
        while not done:
            if "QUESTION" in obs:
                obs, reward, done, info = env.step({
                    "tool": "submit_answer",
                    "args": {"answer": "I don't have enough information"}
                })
            else:
                obs, reward, done, info = env.step({"tool": "next"})
            steps += 1
            if steps > 200:
                break
        assert done

    def test_forget_works(self):
        env = MemoryEnv("company", seed=0)
        env.reset()
        _, _, _, info = env.step({
            "tool": "memory_store",
            "args": {"content": "temp data"}
        })
        mid = info["memory_id"]
        _, _, _, info = env.step({
            "tool": "memory_forget",
            "args": {"memory_id": mid}
        })
        assert info["deleted"] is True
        # Search should find nothing
        _, _, _, info = env.step({
            "tool": "memory_search",
            "args": {"query": "temp data"}
        })
        assert len(info["results"]) == 0

    def test_tier_lite(self):
        env = MemoryEnv("company", tier="lite", seed=0)
        assert env.n_entities == 30
        assert env.n_questions == 10
        assert env.n_corrections == 3
        assert env.write_budget == 15

    def test_tier_standard(self):
        env = MemoryEnv("company", tier="standard", seed=0)
        assert env.n_entities == 60
        assert env.n_questions == 20
        assert env.n_corrections == 5
        assert env.write_budget == 30

    def test_tier_hard(self):
        env = MemoryEnv("company", tier="hard", seed=0)
        assert env.n_entities == 120
        assert env.n_questions == 40
        assert env.n_corrections == 10
        assert env.write_budget == 30

    def test_invalid_tier_raises(self):
        try:
            MemoryEnv("company", tier="impossible", seed=0)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "impossible" in str(e)

    def test_episode_stats_in_info(self):
        env = MemoryEnv("company", seed=0, n_entities=10, n_questions=5)
        env.reset()
        obs, _, _, info = env.step({"tool": "next"})
        assert "episode_stats" in info
        stats = info["episode_stats"]
        assert stats["writes_used"] == 0
        assert stats["budget_remaining"] == env.write_budget
        assert stats["questions_answered"] == 0
        assert stats["correct_count"] == 0
        assert stats["total_questions"] > 0

    def test_get_verifiable_reward(self):
        env = MemoryEnv("company", seed=0, n_entities=10, n_questions=5)
        env.reset()
        # Before any questions answered, reward = 0
        assert env.get_verifiable_reward() == 0.0

    def test_budget_context_in_observation(self):
        env = MemoryEnv("company", tier="lite", seed=0)
        obs = env.reset()
        assert "Budget:" in obs
        assert "Corrections coming:" in obs
        assert "Suggestion:" in obs

    def test_eval_salt_changes_values(self):
        """eval_salt must perturb entity values to prevent RL memorization."""
        env0 = MemoryEnv("company", seed=0, n_entities=10,
                         n_questions=3, eval_salt=0)
        env0.reset(seed=0)
        vals0 = {e.name: dict(e.attrs) for e in env0._world.entities}

        env1 = MemoryEnv("company", seed=0, n_entities=10,
                         n_questions=3, eval_salt=99)
        env1.reset(seed=0)
        vals1 = {e.name: dict(e.attrs) for e in env1._world.entities}

        # Same entity names
        assert set(vals0.keys()) == set(vals1.keys())
        # Values must differ
        changed = 0
        total = 0
        for name in vals0:
            for attr in vals0[name]:
                if vals0[name][attr] is not None:
                    total += 1
                    if vals0[name][attr] != vals1[name].get(attr):
                        changed += 1
        assert changed > total * 0.5, (
            f"eval_salt changed only {changed}/{total} values")

    def test_episode_complete_text(self):
        env = MemoryEnv("company", seed=0, n_entities=10, n_questions=5)
        obs = env.reset()
        done = False
        steps = 0
        while not done:
            if "QUESTION" in obs:
                obs, _, done, _ = env.step({
                    "tool": "submit_answer",
                    "args": {"answer": "I don't have enough information"}
                })
            else:
                obs, _, done, _ = env.step({"tool": "next"})
            steps += 1
            if steps > 200:
                break
        assert done
        assert obs == "Episode complete."
