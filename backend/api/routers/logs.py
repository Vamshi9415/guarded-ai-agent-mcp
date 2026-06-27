# backend/api/routers/logs.py
"""Audit log routes for the FastAPI admin backend."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from backend.api.dependencies import get_policy_store
from backend.api.schemas import LogResponse, to_log_response
from backend.policy.store import PolicyStore

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[LogResponse])
async def list_logs(
    conversation_id: str | None = Query(default=None),
    store: PolicyStore = Depends(get_policy_store),
) -> list[LogResponse]:
    """Returns audit logs, optionally filtered to one conversation."""
    logs = await store.get_logs(conversation_id=conversation_id)
    return [to_log_response(log) for log in logs]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_logs(
    conversation_id: str | None = Query(default=None),
    store: PolicyStore = Depends(get_policy_store),
) -> Response:
    """Clears audit logs globally or for one conversation."""
    await store.clear_logs(conversation_id=conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)