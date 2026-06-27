# backend/api/dependencies.py
"""Dependency providers for the FastAPI admin backend.

This module is the only place in the API layer that owns long-lived dependency
instances. Routers obtain everything through FastAPI's dependency injection so
the API surface stays thin and the underlying policy components remain easily
swappable later.
"""

from __future__ import annotations

from functools import lru_cache

from backend.policy.approvals import ApprovalManager
from backend.policy.engine import PolicyEngine
from backend.policy.store import InMemoryPolicyStore, PolicyStore


@lru_cache(maxsize=1)
def get_policy_store() -> PolicyStore:
    """Returns the shared policy store instance for the API process.

    The in-memory store is intentionally process-local for now, but this
    provider shape allows a database-backed PolicyStore implementation to
    replace it later without changing router code.
    """
    return InMemoryPolicyStore()


@lru_cache(maxsize=1)
def get_approval_manager() -> ApprovalManager:
    """Returns the shared approval manager bound to the shared store."""
    return ApprovalManager(get_policy_store())


@lru_cache(maxsize=1)
def get_policy_engine() -> PolicyEngine:
    """Returns the shared policy engine bound to the shared store."""
    return PolicyEngine(
        store=get_policy_store(),
        approval_manager=get_approval_manager(),
    )