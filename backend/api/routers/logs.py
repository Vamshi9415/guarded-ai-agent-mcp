# backend/api/routers/logs.py
"""Audit log routes for the FastAPI admin backend.

DELETE /logs is intentionally omitted: audit logs are append-only by design.
Exposing a delete endpoint would let callers erase the audit trail, which
defeats the purpose of having one. Re-add only if the assignment explicitly
requires it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_policy_store
from backend.api.schemas import LogResponse, to_log_response
from backend.policy.store import PolicyStore

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=list[LogResponse])
async def list_logs(
    conversation_id: str | None = Query(default=None),
    store: PolicyStore = Depends(get_policy_store),
) -> list[LogResponse]:
    """Returns audit logs, optionally filtered to one conversation."""
    logs = await store.get_logs(conversation_id=conversation_id)
    return [to_log_response(log) for log in logs]
