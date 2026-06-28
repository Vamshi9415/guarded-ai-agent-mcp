# backend/api/tests/conftest.py
"""Shared pytest fixtures for the API test suite.

Every test gets a fresh InMemoryPolicyStore (and matching ApprovalManager)
injected via FastAPI's dependency_overrides, so tests are fully isolated with
no shared state between them.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.api.dependencies import get_approval_manager, get_policy_store
from backend.policy.approvals import ApprovalManager
from backend.policy.store import InMemoryPolicyStore


@pytest.fixture()
def store() -> InMemoryPolicyStore:
    return InMemoryPolicyStore()


@pytest.fixture()
def approval_manager(store: InMemoryPolicyStore) -> ApprovalManager:
    return ApprovalManager(store)


@pytest.fixture()
def client(store: InMemoryPolicyStore, approval_manager: ApprovalManager) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_policy_store] = lambda: store
    app.dependency_overrides[get_approval_manager] = lambda: approval_manager
    return TestClient(app)
