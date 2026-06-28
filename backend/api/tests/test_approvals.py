# backend/api/tests/test_approvals.py
"""Tests for the /api/approvals router."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.policy.approvals import ApprovalManager
from backend.policy.store import InMemoryPolicyStore


def _submit_approval(store: InMemoryPolicyStore) -> str:
    """Helper: synchronously submits a test approval and returns its id."""
    manager = ApprovalManager(store)
    request = asyncio.get_event_loop().run_until_complete(
        manager.submit_request(
            conversation_id="conv-1",
            tool_name="delete_record",
            arguments={"key": "user_1"},
            matched_rule_id="rule-abc",
            timeout_seconds=60,
        )
    )
    return request.id


def test_list_pending_empty(client: TestClient) -> None:
    response = client.get("/api/approvals/pending")
    assert response.status_code == 200
    assert response.json() == []


def test_list_all_empty(client: TestClient) -> None:
    response = client.get("/api/approvals")
    assert response.status_code == 200
    assert response.json() == []


def test_list_pending_after_submit(
    client: TestClient,
    store: InMemoryPolicyStore,
) -> None:
    _submit_approval(store)
    response = client.get("/api/approvals/pending")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_all_after_submit(
    client: TestClient,
    store: InMemoryPolicyStore,
) -> None:
    _submit_approval(store)
    response = client.get("/api/approvals")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_approve_request(
    client: TestClient,
    store: InMemoryPolicyStore,
) -> None:
    approval_id = _submit_approval(store)
    response = client.post(
        f"/api/approvals/{approval_id}/approve",
        json={"resolved_by": "admin", "reason": "looks fine"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["resolved_by"] == "admin"


def test_reject_request(
    client: TestClient,
    store: InMemoryPolicyStore,
) -> None:
    approval_id = _submit_approval(store)
    response = client.post(
        f"/api/approvals/{approval_id}/reject",
        json={"resolved_by": "admin", "reason": "not allowed"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"


def test_approve_not_found(client: TestClient) -> None:
    response = client.post(
        "/api/approvals/does-not-exist/approve",
        json={"resolved_by": "admin"},
    )
    assert response.status_code == 404
