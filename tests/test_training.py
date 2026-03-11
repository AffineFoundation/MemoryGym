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
            m["content"].count('"Write"')
            for m in perfect if m["role"] == "assistant"
        )
        strategic_stores = sum(
            m["content"].count('"Write"')
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
        assert "Budget:" in obs
        assert "selective" in obs

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

    def test_shaped_reward_store_with_entity_name(self):
        """Shaped mode: storing content with entity name → positive reward."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, reward_mode="shaped")
        obs = env.reset()
        # First event should be ingest with entity names
        assert "DOCUMENTS" in obs
        # Get entity names from stream
        names = env._stream[0].get("entity_names", [])
        assert len(names) > 0
        # Store content containing an entity name
        _, reward, _, info = env.step({
            "tool": "memory_store",
            "args": {"content": f"{names[0]} has revenue of $500M"}
        })
        assert reward == 0.3, f"Expected 0.3 for relevant store, got {reward}"
        assert "memory_id" in info

    def test_shaped_reward_budget_exhausted(self):
        """Shaped mode: writing past budget → penalty."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, write_budget=1, reward_mode="shaped")
        env.reset()
        # Use up the single write
        env.step({"tool": "memory_store", "args": {"content": "data"}})
        # Second write should fail with penalty
        _, reward, _, info = env.step({
            "tool": "memory_store", "args": {"content": "more data"}
        })
        assert reward == -0.05
        assert "error" in info

    def test_shaped_reward_correction_flow(self):
        """Shaped mode: Edit during correction → +0.5."""
        env = MemoryEnv("company", seed=0, n_entities=30,
                        n_questions=5, reward_mode="shaped")
        env.reset()
        # Advance to first correction event
        while env._event_idx < len(env._stream):
            if env._stream[env._event_idx]["type"] == "correction":
                break
            env.step({"tool": "next"})
        if env._event_idx >= len(env._stream):
            return  # No corrections in this stream
        # Store something first so Edit has content to find
        env.step({"tool": "Write",
                  "args": {"content": "some entity data"}})
        # Edit replaces old content → 0.5 correction reward
        _, reward, _, _ = env.step({
            "tool": "Edit",
            "args": {"old_text": "some entity", "new_text": "corrected entity"}
        })
        assert reward == 0.5

    def test_binary_mode_unchanged(self):
        """Binary mode: no intermediate rewards, only submit_answer."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, reward_mode="binary")
        env.reset()
        names = env._stream[0].get("entity_names", [])
        # Store should give 0 reward in binary mode
        _, reward, _, _ = env.step({
            "tool": "memory_store",
            "args": {"content": f"{names[0]} data"}
        })
        assert reward == 0.0

    def test_tier_multi(self):
        env = MemoryEnv("company", tier="multi", seed=0)
        assert env.n_entities == 60
        assert env.n_questions == 20
        assert env.n_sessions == 3

    def test_multi_session_episode(self):
        """Multi-session: episode runs to completion with session breaks."""
        env = MemoryEnv("company", tier="multi", seed=0,
                        n_entities=30, n_questions=10)
        obs = env.reset()
        assert isinstance(obs, str)

        done = False
        steps = 0
        session_breaks_seen = 0
        stored_before_break = False
        found_after_break = False

        while not done:
            if "SESSION BREAK" in obs:
                session_breaks_seen += 1
                # After session break, search should still find stored data
                if stored_before_break:
                    obs, _, done, info = env.step({
                        "tool": "memory_search",
                        "args": {"query": "test entity"}
                    })
                    if info["results"]:
                        found_after_break = True
                    steps += 1
                    if done:
                        break
                obs, _, done, info = env.step({"tool": "next"})
            elif "QUESTION" in obs:
                obs, _, done, _ = env.step({
                    "tool": "submit_answer",
                    "args": {"answer": "I don't have enough information"}
                })
            elif "DOCUMENTS" in obs and not stored_before_break:
                # Store something in first session
                obs, _, done, _ = env.step({
                    "tool": "memory_store",
                    "args": {"content": "test entity | revenue: 1000"}
                })
                stored_before_break = True
            else:
                obs, _, done, _ = env.step({"tool": "next"})
            steps += 1
            if steps > 300:
                break
        assert done, "Episode did not complete"
        assert session_breaks_seen >= 1, "No session breaks in multi-session"
        # Memory backend persists across sessions
        if stored_before_break:
            assert found_after_break, (
                "Memory backend did not persist across session break")

    def test_noise_event_format(self):
        """Noise events should render as [INFO] not [DONE]."""
        env = MemoryEnv("company", tier="lite", seed=0)
        env.reset()
        # Find a noise event in the stream
        for i, event in enumerate(env._stream):
            if event["type"] == "noise":
                env._event_idx = i
                text = env._format_event(event)
                assert "[INFO]" in text
                assert "supplementary" in text.lower()
                assert "[DONE]" not in text
                return
        # If no noise in this seed, try another
        env2 = MemoryEnv("company", tier="standard", seed=0)
        env2.reset()
        noise_events = [e for e in env2._stream if e["type"] == "noise"]
        assert len(noise_events) > 0, "No noise events found in stream"

    def test_sft_trajectory_handles_noise_events(self):
        """SFT trajectory includes noise events as user+assistant messages."""
        messages = generate_sft_trajectory("company", seed=0)
        # Check that noise info events appear in trajectory
        info_msgs = [m for m in messages if m["role"] == "user"
                     and "[INFO]" in m["content"]]
        assert len(info_msgs) > 0, "SFT trajectory missing noise events"

    def test_reward_mode_validation(self):
        """Invalid reward_mode raises ValueError."""
        try:
            MemoryEnv("company", reward_mode="invalid")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "invalid" in str(e)

    def test_backend_type_chromadb(self):
        """MemoryEnv with backend_type='chromadb' works (default)."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, backend_type="chromadb")
        obs = env.reset()
        assert "DOCUMENTS" in obs or "Event" in obs
        _, _, _, info = env.step({
            "tool": "memory_store",
            "args": {"content": "test data"}
        })
        assert "memory_id" in info

    def test_backend_type_attribute(self):
        """MemoryEnv stores backend_type for inspection."""
        env = MemoryEnv("company", seed=0, backend_type="chromadb")
        assert env._backend_type == "chromadb"

    def test_duplicate_store_penalty(self):
        """Shaped mode: storing same entity twice → negative reward."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, reward_mode="shaped")
        env.reset()
        names = env._stream[0].get("entity_names", [])
        assert len(names) > 0
        name = names[0]
        # First store → positive
        _, r1, _, _ = env.step({
            "tool": "memory_store",
            "args": {"content": f"{name} | revenue: 500"}
        })
        assert r1 == 0.3
        # Second store of same entity → penalty
        _, r2, _, _ = env.step({
            "tool": "memory_store",
            "args": {"content": f"{name} | updated revenue: 600"}
        })
        assert r2 == -0.1

    def test_efficiency_bonus(self):
        """Shaped mode: unique entities / writes → efficiency bonus."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, reward_mode="shaped")
        env.reset()
        names = env._stream[0].get("entity_names", [])
        assert len(names) >= 2
        # Store two unique entities in two writes → efficiency = 1.0
        env.step({
            "tool": "memory_store",
            "args": {"content": f"{names[0]} | data A"}
        })
        env.step({
            "tool": "memory_store",
            "args": {"content": f"{names[1]} | data B"}
        })
        reward = env.get_verifiable_reward()
        # Base is 0 (no questions answered), bonus = min(2/2, 1.0) * 0.2 = 0.2
        assert abs(reward - 0.2) < 1e-9

    def test_correction_speed_reward(self):
        """Shaped mode: immediate search after correction → +0.1."""
        env = MemoryEnv("company", seed=0, n_entities=30,
                        n_questions=5, reward_mode="shaped")
        env.reset()
        # Advance to first correction event
        while env._event_idx < len(env._stream):
            if env._stream[env._event_idx]["type"] == "correction":
                break
            env.step({"tool": "next"})
        if env._event_idx >= len(env._stream):
            return  # No corrections in this stream
        # Immediate search after correction → speed reward
        _, reward, _, _ = env.step({
            "tool": "memory_search",
            "args": {"query": "entity"}
        })
        assert reward == 0.1

    def test_reset_cleans_old_chromadb_collection(self):
        """Multiple reset() calls should not leak ChromaDB collections."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, backend_type="chromadb")
        env.reset(seed=0)
        # Store something so collection isn't empty
        env.step({"tool": "Write", "args": {"content": "entity A data"}})
        old_client = env._backend._client
        old_name = env._backend._collection.name
        # Reset creates new backend, old collection should be cleaned up
        env.reset(seed=1)
        # Old collection should no longer exist
        existing_names = [c.name for c in old_client.list_collections()]
        assert old_name not in existing_names, (
            f"Old collection {old_name} still exists after reset()")
        env.close()

    def test_reset_cleans_old_markdown_tmpdir(self):
        """Multiple reset() calls should not leak /tmp directories."""
        import os
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, backend_type="markdown")
        env.reset(seed=0)
        old_dir = env._backend._dir
        assert old_dir.exists()
        # Reset should clean up old temp dir
        env.reset(seed=1)
        assert not old_dir.exists(), (
            f"Old temp dir {old_dir} still exists after reset()")
        env.close()

    def test_env_close_cleans_up(self):
        """MemoryEnv.close() cleans up backend resources."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, backend_type="markdown")
        env.reset(seed=0)
        tmpdir = env._backend._dir
        assert tmpdir.exists()
        env.close()
        assert not tmpdir.exists()

    def test_chromadb_edit_miss_refunds_budget(self):
        """ChromaDB Edit with wrong old_text should refund budget."""
        env = MemoryEnv("company", seed=0, n_entities=10,
                        n_questions=3, backend_type="chromadb")
        env.reset(seed=0)
        # Store an entity
        env.step({"tool": "Write",
                  "args": {"content": "Company A | Revenue: 500"}})
        writes_after_store = env._writes_used
        # Edit with non-matching old_text
        _, _, _, info = env.step({
            "tool": "Edit",
            "args": {"old_text": "Revenue: 999", "new_text": "Revenue: 600"}
        })
        assert info.get("error") == "Text not found in memory"
        assert info.get("edited") is False
        # Budget should be refunded
        assert env._writes_used == writes_after_store
        # Original content should be unchanged
        results = env._backend.search("Company A", top_k=1)
        assert "500" in results[0]["content"]
        env.close()

    def test_sft_respects_budget(self):
        """SFT trajectory Write calls must not exceed write_budget."""
        for strategy in ("perfect", "strategic"):
            messages = generate_sft_trajectory(
                "company", seed=0, n_entities=60,
                write_budget=30, strategy=strategy,
            )
            write_count = sum(
                1 for m in messages
                if m["role"] == "assistant" and '"name": "Write"' in m["content"]
            )
            assert write_count <= 30, (
                f"strategy={strategy}: {write_count} Writes > budget 30"
            )

    def test_sft_json_dumps_all_queries(self):
        """All tool call arguments in SFT trajectory must use json.dumps."""
        import re
        messages = generate_sft_trajectory("company", seed=0)
        for m in messages:
            if m["role"] != "assistant":
                continue
            # Find any bare (non-json.dumps) string in arguments
            # Pattern: "query": "..." without proper escaping
            # A properly json.dumps'd value won't have unescaped quotes
            for call in re.findall(r'<tool_call>(.*?)</tool_call>', m["content"]):
                parsed = json.loads(call)
                # All argument values should be valid — this verifies
                # json.dumps was used (no raw f-string injection)
                assert isinstance(parsed["arguments"], dict)
