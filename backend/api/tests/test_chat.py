# backend/api/tests/test_chat.py
"""Tests for the /api/chat router.

These tests use a mock ToolLoop so they never make real Gemini or MCP calls.
The AgentManager is injected fresh per test via dependency_overrides so there
is no shared state between tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.agent.agent_manager import AgentManager
from backend.agent.tool_loop import ToolLoop, StopReason, ToolLoopResult
from backend.api.app import create_app
from backend.api.dependencies import get_agent_manager
from backend.llm.base import Message


def _make_tool_loop(reply: str = "Hello from the agent.") -> ToolLoop:
    """Returns a ToolLoop whose run() always returns a fixed reply.

    Uses MagicMock so no LLM or MCP calls are made.
    """
    async def run(messages, conversation_id):
        return ToolLoopResult(
            messages=[*messages, Message.assistant(text=reply)],
            final_text=reply,
            tool_turns_used=0,
            stop_reason=StopReason.COMPLETED,
        )

    loop = MagicMock(spec=ToolLoop)
    loop.run = AsyncMock(side_effect=run)
    return loop

@pytest.fixture()
def agent_manager() -> AgentManager:
    return AgentManager(tool_loop=_make_tool_loop())


@pytest.fixture()
def client(agent_manager: AgentManager) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_agent_manager] = lambda: agent_manager
    # Disable lifespan so the test client doesn't try to connect MCP.
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

def test_chat_new_conversation(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": "Hello"})
    assert response.status_code == 200
    body = response.json()
    assert "conversation_id" in body
    assert body["reply"] == "Hello from the agent."


def test_chat_returns_stable_conversation_id(client: TestClient) -> None:
    """Second message with the same id should reuse the same conversation."""
    first = client.post("/api/chat", json={"message": "First message"})
    cid = first.json()["conversation_id"]

    second = client.post("/api/chat", json={"conversation_id": cid, "message": "Second message"})
    assert second.status_code == 200
    assert second.json()["conversation_id"] == cid


def test_chat_unknown_conversation_id_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/chat",
        json={"conversation_id": "does-not-exist", "message": "Hello"},
    )
    assert response.status_code == 404


def test_chat_empty_message_rejected(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_missing_message_rejected(client: TestClient) -> None:
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/chat/conversations
# ---------------------------------------------------------------------------

def test_list_conversations_empty(client: TestClient) -> None:
    response = client.get("/api/chat/conversations")
    assert response.status_code == 200
    assert response.json() == []


def test_list_conversations_after_chat(client: TestClient) -> None:
    client.post("/api/chat", json={"message": "Hi"})
    response = client.get("/api/chat/conversations")
    assert response.status_code == 200
    assert len(response.json()) == 1
    entry = response.json()[0]
    assert "conversation_id" in entry
    assert "created_at" in entry
    assert "message_count" in entry


def test_list_conversations_counts_messages(client: TestClient) -> None:
    first = client.post("/api/chat", json={"message": "Turn 1"})
    cid = first.json()["conversation_id"]
    client.post("/api/chat", json={"conversation_id": cid, "message": "Turn 2"})

    convs = client.get("/api/chat/conversations").json()
    match = next(c for c in convs if c["conversation_id"] == cid)
    assert match["message_count"] == 2


# ---------------------------------------------------------------------------
# POST /api/chat/{conversation_id}/reset
# ---------------------------------------------------------------------------

def test_reset_conversation(client: TestClient) -> None:
    first = client.post("/api/chat", json={"message": "Turn 1"})
    cid = first.json()["conversation_id"]

    reset = client.post(f"/api/chat/{cid}/reset")
    assert reset.status_code == 200
    assert reset.json()["message_count"] == 0
    assert reset.json()["conversation_id"] == cid


def test_reset_unknown_conversation_returns_404(client: TestClient) -> None:
    response = client.post("/api/chat/does-not-exist/reset")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/chat/{conversation_id}
# ---------------------------------------------------------------------------

def test_delete_conversation(client: TestClient) -> None:
    first = client.post("/api/chat", json={"message": "Hi"})
    cid = first.json()["conversation_id"]

    delete = client.delete(f"/api/chat/{cid}")
    assert delete.status_code == 204

    # Conversation should be gone — follow-up message returns 404.
    follow = client.post("/api/chat", json={"conversation_id": cid, "message": "Still here?"})
    assert follow.status_code == 404


def test_delete_unknown_conversation_returns_404(client: TestClient) -> None:
    response = client.delete("/api/chat/does-not-exist")
    assert response.status_code == 404

