# backend/api/tests/test_rules.py
"""Tests for the /api/rules router."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


VALID_RULE = {
    "name": "block-delete",
    "action": "BLOCK",
    "tool_pattern": "delete_*",
    "rule_type": "GLOB",
    "priority": 10,
    "enabled": True,
    "constraints": [],
    "approval_timeout_seconds": 300,
    "reason": "deletes are never allowed",
    "description": None,
    "scope": "global",
    "scope_id": None,
}


def test_list_rules_empty(client: TestClient) -> None:
    response = client.get("/api/rules")
    assert response.status_code == 200
    assert response.json() == []


def test_create_rule_returns_201(client: TestClient) -> None:
    response = client.post("/api/rules", json=VALID_RULE)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "block-delete"
    assert body["action"] == "BLOCK"
    assert "id" in body


def test_get_rule_round_trip(client: TestClient) -> None:
    created = client.post("/api/rules", json=VALID_RULE).json()
    rule_id = created["id"]

    fetched = client.get(f"/api/rules/{rule_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == rule_id


def test_get_rule_not_found(client: TestClient) -> None:
    response = client.get("/api/rules/does-not-exist")
    assert response.status_code == 404


def test_create_rule_empty_name_rejected(client: TestClient) -> None:
    payload = {**VALID_RULE, "name": ""}
    response = client.post("/api/rules", json=payload)
    assert response.status_code == 422


def test_create_rule_invalid_action_rejected(client: TestClient) -> None:
    payload = {**VALID_RULE, "action": "deny"}   # "deny" is NOT a valid RuleAction
    response = client.post("/api/rules", json=payload)
    assert response.status_code == 422


def test_create_rule_validation_error_is_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    payload = {"name": "missing-tool-pattern"}
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/rules", json=payload)

    assert response.status_code == 422
    assert "Request validation failed POST /api/rules" in caplog.text


def test_update_rule(client: TestClient) -> None:
    created = client.post("/api/rules", json=VALID_RULE).json()
    rule_id = created["id"]

    updated_payload = {**VALID_RULE, "name": "block-delete-updated", "priority": 99}
    response = client.put(f"/api/rules/{rule_id}", json=updated_payload)
    assert response.status_code == 200
    assert response.json()["name"] == "block-delete-updated"
    assert response.json()["priority"] == 99


def test_delete_rule(client: TestClient) -> None:
    created = client.post("/api/rules", json=VALID_RULE).json()
    rule_id = created["id"]

    delete_resp = client.delete(f"/api/rules/{rule_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/rules/{rule_id}")
    assert get_resp.status_code == 404


def test_enable_disable_rule(client: TestClient) -> None:
    created = client.post("/api/rules", json={**VALID_RULE, "enabled": True}).json()
    rule_id = created["id"]

    disabled = client.patch(f"/api/rules/{rule_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    enabled = client.patch(f"/api/rules/{rule_id}/enable")
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True


def test_list_rules_after_create(client: TestClient) -> None:
    client.post("/api/rules", json=VALID_RULE)
    client.post("/api/rules", json={**VALID_RULE, "name": "allow-list"})
    response = client.get("/api/rules")
    assert response.status_code == 200
    assert len(response.json()) == 2
