# backend/api/tests/test_budgets.py
"""Tests for the /api/budgets router."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_get_default_budget(client: TestClient) -> None:
    response = client.get("/api/budgets/default")
    assert response.status_code == 200
    body = response.json()
    assert "max_tokens" in body


def test_list_budgets_empty_returns_default_only(client: TestClient) -> None:
    response = client.get("/api/budgets")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 0


def test_set_default_budget(client: TestClient) -> None:
    response = client.put("/api/budgets/default", json={"max_tokens": 5000})
    assert response.status_code == 200
    assert response.json()["max_tokens"] == 5000


def test_list_budgets_after_updates(client: TestClient) -> None:
    client.put("/api/budgets/default", json={"max_tokens": 5000})
    client.put("/api/budgets/conv-123", json={"max_tokens": 2000})
    response = client.get("/api/budgets")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_reset_conversation_budget(client: TestClient) -> None:
    client.put("/api/budgets/conv-123", json={"max_tokens": 2000})
    response = client.delete("/api/budgets/conv-123")
    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conv-123"


def test_set_budget_invalid_zero_rejected(client: TestClient) -> None:
    response = client.put("/api/budgets/default", json={"max_tokens": 0})
    assert response.status_code == 422


def test_set_budget_invalid_negative_rejected(client: TestClient) -> None:
    response = client.put("/api/budgets/default", json={"max_tokens": -100})
    assert response.status_code == 422


def test_set_conversation_budget(client: TestClient) -> None:
    response = client.put("/api/budgets/conv-123", json={"max_tokens": 2000})
    assert response.status_code == 200
    assert response.json()["max_tokens"] == 2000


def test_get_conversation_budget(client: TestClient) -> None:
    client.put("/api/budgets/conv-456", json={"max_tokens": 3000})
    response = client.get("/api/budgets/conv-456")
    assert response.status_code == 200
    assert response.json()["max_tokens"] == 3000


def test_get_budget_state(client: TestClient) -> None:
    response = client.get("/api/budgets/conv-999/state")
    assert response.status_code == 200
    body = response.json()
    assert body["total_tokens"] == 0
