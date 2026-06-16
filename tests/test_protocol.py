"""Tests for memorygym.protocol rollout export helpers."""

from __future__ import annotations

import json

from memorygym.protocol import trajectory_to_conversation


def test_trajectory_to_conversation_exports_tool_calls_and_tool_role():
    trajectory = [
        {
            "type": "documents",
            "content": "=== Event 1/2 [DOCUMENTS] ===",
            "turns": [
                {
                    "role": "assistant",
                    "content": "storing facts",
                    "tool_calls": [
                        {
                            "name": "memory",
                            "arguments": {
                                "action": "add",
                                "target": "memory",
                                "topic": "ingest_1",
                                "content": "Entity | attr: value",
                            },
                        },
                        {
                            "name": "memory",
                            "arguments": {
                                "action": "search",
                                "target": "memory",
                                "topic": "ingest_1",
                                "query": "Entity",
                            },
                        },
                    ],
                    "tool_results": [
                        '[tool] {"ok":true,"message":"entry added","topic":"ingest_1"}',
                        '[tool] {"ok":true,"message":"1 result(s)","topic":"ingest_1"}',
                    ],
                }
            ],
        }
    ]

    conversation = trajectory_to_conversation(trajectory)

    assert conversation[0] == {
        "role": "user",
        "content": "=== Event 1/2 [DOCUMENTS] ===",
    }

    assistant = conversation[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "storing facts"
    assert len(assistant["tool_calls"]) == 2
    assert assistant["tool_calls"][0]["id"] == "call_0"
    assert assistant["tool_calls"][0]["function"]["name"] == "memory"
    add_args = json.loads(assistant["tool_calls"][0]["function"]["arguments"])
    assert add_args["action"] == "add"
    assert add_args["topic"] == "ingest_1"

    tool_add = conversation[2]
    assert tool_add["role"] == "tool"
    assert tool_add["tool_call_id"] == "call_0"
    assert tool_add["name"] == "memory"
    assert '"entry added"' in tool_add["content"]
    assert not tool_add["content"].startswith("[tool]")

    tool_search = conversation[3]
    assert tool_search["role"] == "tool"
    assert tool_search["tool_call_id"] == "call_1"
    search_args = json.loads(assistant["tool_calls"][1]["function"]["arguments"])
    assert search_args["action"] == "search"
    assert search_args["query"] == "Entity"


def test_trajectory_to_conversation_keeps_system_message():
    trajectory = [
        {"type": "system", "content": "system rules"},
        {
            "type": "question",
            "content": "Question?",
            "turns": [
                {
                    "role": "assistant",
                    "content": "answer",
                    "tool_calls": [],
                    "tool_results": [],
                }
            ],
        },
    ]

    conversation = trajectory_to_conversation(trajectory)

    assert conversation[0] == {"role": "system", "content": "system rules"}
    assert conversation[1] == {"role": "user", "content": "Question?"}
    assert conversation[2] == {"role": "assistant", "content": "answer"}
