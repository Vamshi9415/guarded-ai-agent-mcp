# backend/api/routers/approvals.py
"""Approval management routes for the FastAPI admin backend."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_approval_manager, get_policy_store
from backend.api.schemas import (
    ApprovalDecision,
    ApprovalResponse,
    to_approval_response,
)
from backend.policy.approvals import ApprovalManager
from backend.policy.store import PolicyStore

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _not_found(detail: str) -> HTTPException:
    """Builds a 404 HTTP exception."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


@router.get("/pending", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    store: PolicyStore = Depends(get_policy_store),
) -> list[ApprovalResponse]:
    """Returns all currently pending approval requests."""
    approvals = await store.list_pending_approvals()
    return [to_approval_response(approval) for approval in approvals]


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: str,
    payload: ApprovalDecision,
    approvals: ApprovalManager = Depends(get_approval_manager),
) -> ApprovalResponse:
    """Approves a pending approval request."""
    try:
        resolved = await approvals.approve(
            approval_id=approval_id,
            approver=payload.approver,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return to_approval_response(resolved)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: str,
    payload: ApprovalDecision,
    approvals: ApprovalManager = Depends(get_approval_manager),
) -> ApprovalResponse:
    """Rejects a pending approval request."""
    try:
        resolved = await approvals.reject(
            approval_id=approval_id,
            approver=payload.approver,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise _not_found(str(exc)) from exc

    return to_approval_response(resolved)