# backend/api/tests/test_health.py
"""Tests for the root (/) and health (/health) endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "name" in body
    assert "docs" in body
    assert "health" in body


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_health_includes_rule_count(client: TestClient) -> None:
    response = client.get("/health")
    assert "rules" in response.json()
    assert isinstance(response.json()["rules"], int)


def test_health_includes_pending_approvals(client: TestClient) -> None:
    response = client.get("/health")
    assert "pending_approvals" in response.json()
    assert isinstance(response.json()["pending_approvals"], int)


def test_health_includes_version(client: TestClient) -> None:
    response = client.get("/health")
    assert "version" in response.json()
    assert response.json()["version"] == "0.1.0"


def test_health_reports_mongo_storage(client: TestClient) -> None:
    response = client.get("/health")
    body = response.json()
    assert body["storage_backend"] == "mongo"
    assert body["storage_ready"] is True


def test_health_rule_count_reflects_created_rules(client: TestClient) -> None:
    """Rule count in /health must reflect real store state."""
    before = client.get("/health").json()["rules"]
    client.post(
        "/api/rules",
        json={
            "name": "test-rule",
            "action": "BLOCK",
            "tool_pattern": "test_*",
            "rule_type": "GLOB",
            "priority": 0,
            "enabled": True,
            "constraints": [],
            "approval_timeout_seconds": 300,
            "reason": None,
            "description": None,
            "scope": "global",
            "scope_id": None,
        },
    )
    after = client.get("/health").json()["rules"]
    assert after == before + 1
