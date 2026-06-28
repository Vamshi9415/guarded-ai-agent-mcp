# backend/policy/approvals.py
"""
Lifecycle management for human-approval gates.

ApprovalManager turns "a REQUIRE_APPROVAL rule matched" into a concrete,
awaitable ApprovalRequest, and resolves it - by an admin approving,
rejecting, or by its own deadline passing - without anyone polling or
sleeping. It knows nothing about MCP, ToolLoop, Gemini, dashboards,
budgets, rule matching, or constraint evaluation; it only coordinates
ApprovalRequest objects through a PolicyStore. engine.py is the only
caller expected to know this class exists.

Design choices:

  - asyncio.Event, not asyncio.Condition: every waiter on one approval
    is blocked on the exact same one-shot transition (PENDING -> a
    terminal status), which happens at most once per approval. That's
    Event's use case. Condition earns its keep when waiters block on
    *different* predicates over shared state; there's only one predicate
    here, so Condition would add machinery with nothing to spend it on.

  - One Lock + one Event per approval id, not one global pair: keeps
    unrelated approvals from contending with each other at all, and is
    what makes "multiple concurrent approvals" genuinely concurrent
    rather than merely safe.

  - The per-id dict lookups themselves (_get_event, _get_lock) are
    deliberately synchronous and unlocked. dict.setdefault() has no
    `await` inside it, so under asyncio's cooperative scheduling no
    other task can interleave between the lookup and the insert - the
    same reasoning that justified store.py's lock-free reads. The
    per-id Lock exists for a different reason: the *resolution*
    critical section spans real awaits to the store (read status, then
    write status), and that's where two callers really could race.

  - expires_at is never recomputed here. It was set once, at creation,
    in submit_request (from a timeout the *caller* supplies). 
    wait_for_resolution only ever reads it.

Independence note, consistent with the rest of backend/policy/*: this
file imports from .models and .store (sibling modules in this package)
and nothing from backend.agent, backend.llm, or backend.mcp.

Known scope limits:
  - Notification is in-process only. approve()/reject() must be called
    on the same ApprovalManager instance a waiter is blocked on.
  - Per-id Lock/Event entries are never removed, so a process that runs
    for a very long time accumulates one of each per approval ever
    created. Safe, just unbounded.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from typing import Any

from .models import ApprovalRequest, ApprovalStatus, _utcnow
from .store import PolicyStore


class ApprovalManager:
    """Coordinates ApprovalRequest lifecycle through an injected
    PolicyStore. Holds no rule, budget, or tool-execution knowledge -
    only what's needed to create, wait on, and resolve approvals.
    """

    def __init__(self, store: PolicyStore):
        self.store = store

        self._events: dict[str, asyncio.Event] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    async def submit_request(
        self,
        *,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        matched_rule_id: str,
        timeout_seconds: int,
    ) -> ApprovalRequest:
        """Creates and persists a new pending ApprovalRequest."""
        now = _utcnow()
        request = ApprovalRequest(
            conversation_id=conversation_id,
            tool_name=tool_name,
            arguments=arguments,
            matched_rule_id=matched_rule_id,
            expires_at=now + timedelta(seconds=timeout_seconds),
            created_at=now,
        )
        return await self.store.create_approval(request)

    async def find_matching_approval(
        self,
        *,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        matched_rule_id: str,
    ) -> ApprovalRequest | None:
        """Returns the newest approval for the same conversation/tool pair.

        This lets the policy engine reuse an existing approval gate instead of
        creating a new one when the model retries the same tool call.
        """
        approvals = await self.store.list_approvals()

        for approval in reversed(approvals):
            if (
                approval.conversation_id == conversation_id
                and approval.tool_name == tool_name
                and approval.matched_rule_id == matched_rule_id
                and approval.arguments == arguments
            ):
                return approval

        return None

    # ------------------------------------------------------------------
    # Waiting
    # ------------------------------------------------------------------

    async def wait_for_resolution(self, approval_id: str) -> ApprovalRequest:
        """Blocks (without polling) until approval_id reaches APPROVED,
        REJECTED, or TIMED_OUT, then returns the final record."""
        current = await self.store.get_approval(approval_id)
        if current.status is not ApprovalStatus.PENDING:
            return current

        remaining_seconds = (current.expires_at - _utcnow()).total_seconds()

        if remaining_seconds <= 0:
            return await self._resolve(
                approval_id,
                ApprovalStatus.TIMED_OUT,
                resolved_by=None,
                reason="approval window expired before any response",
            )

        event = self._get_event(approval_id)

        try:
            await asyncio.wait_for(event.wait(), timeout=remaining_seconds)
        except asyncio.TimeoutError:
            return await self._resolve(
                approval_id,
                ApprovalStatus.TIMED_OUT,
                resolved_by=None,
                reason="approval window expired before any response",
            )

        return await self.store.get_approval(approval_id)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def approve(
        self,
        approval_id: str,
        *,
        resolved_by: str | None = None,
        reason: str | None = None,
    ) -> ApprovalRequest:
        return await self._resolve(
            approval_id, ApprovalStatus.APPROVED, resolved_by=resolved_by, reason=reason
        )

    async def reject(
        self,
        approval_id: str,
        *,
        resolved_by: str | None = None,
        reason: str | None = None,
    ) -> ApprovalRequest:
        return await self._resolve(
            approval_id, ApprovalStatus.REJECTED, resolved_by=resolved_by, reason=reason
        )

    async def _resolve(
        self,
        approval_id: str,
        status: ApprovalStatus,
        *,
        resolved_by: str | None,
        reason: str | None,
    ) -> ApprovalRequest:
        """Shared transition path. First resolution wins."""
        lock = self._get_lock(approval_id)

        async with lock:
            current = await self.store.get_approval(approval_id)

            if current.status is not ApprovalStatus.PENDING:
                return current

            updated = replace(
                current,
                status=status,
                resolved_at=_utcnow(),
                resolved_by=resolved_by,
                resolution_reason=reason,
            )
            stored = await self.store.update_approval(updated)

        self._get_event(approval_id).set()
        return stored

    # ------------------------------------------------------------------
    # Per-id primitive registries
    # ------------------------------------------------------------------

    def _get_event(self, approval_id: str) -> asyncio.Event:
        return self._events.setdefault(approval_id, asyncio.Event())

    def _get_lock(self, approval_id: str) -> asyncio.Lock:
        return self._locks.setdefault(approval_id, asyncio.Lock())