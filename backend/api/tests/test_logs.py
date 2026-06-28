# backend/api/tests/test_logs.py
"""Tests for the /api/logs router."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.policy.models import DecisionOutcome, PolicyDecisionLog
from backend.policy.store import InMemoryPolicyStore


def _add_log(store: InMemoryPolicyStore, conversation_id: str = "conv-1") -> None:
    """Synchronously appends one log entry to the store."""
    log = PolicyDecisionLog(
        conversation_id=conversation_id,
        tool_name="list_records",
        arguments={},
        outcome=DecisionOutcome.ALLOWED,
        timestamp=datetime.now(tz=timezone.utc),
        execution_time_ms=12.5,
        rewritten_arguments=None,
        reason=None,
        matched_rule_id=None,
    )
    asyncio.get_event_loop().run_until_complete(store.append_log(log))


def test_list_logs_empty(client: TestClient) -> None:
    response = client.get("/api/logs")
    assert response.status_code == 200
    assert response.json() == []


def test_list_logs_returns_entries(
    client: TestClient,
    store: InMemoryPolicyStore,
) -> None:
    _add_log(store)
    _add_log(store)
    response = client.get("/api/logs")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_logs_filtered_by_conversation(
    client: TestClient,
    store: InMemoryPolicyStore,
) -> None:
    _add_log(store, conversation_id="conv-A")
    _add_log(store, conversation_id="conv-B")
    response = client.get("/api/logs?conversation_id=conv-A")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["conversation_id"] == "conv-A"


def test_delete_logs_endpoint_does_not_exist(client: TestClient) -> None:
    """DELETE /api/logs must not be exposed (audit logs are append-only)."""
    response = client.delete("/api/logs")
    assert response.status_code == 405   # Method Not Allowed
