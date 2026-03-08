"""Tests for training data interfaces."""

from __future__ import annotations

import json
from pathlib import Path

from memorybench.training import (
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

    def test_reset_returns_event(self):
        env = MemoryEnv("company", seed=0)
        obs = env.reset()
        assert isinstance(obs, dict)
        assert "type" in obs

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
        done = False
        steps = 0
        while not done:
            if obs["type"] == "question":
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
