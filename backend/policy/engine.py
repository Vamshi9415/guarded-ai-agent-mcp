# backend/policy/engine.py
"""
The real PolicyEngine: wires RuleEvaluator, PolicyStore, and
ApprovalManager into the two methods backend.agent.tool_loop's
PolicyEngine Protocol expects (evaluate, check_budget), plus structured
logging of every decision through PolicyStore.append_log.

This is the only class in backend/policy/* that's allowed to know about
all three of its sibling modules at once - models.py, rules.py, store.py,
and approvals.py each deliberately know nothing about each other beyond
their own direct dependencies; this file is where they actually meet.

Cross-cutting decisions:

  - Naming: this class is named PolicyEngine on purpose, matching
    backend.agent.tool_loop.PolicyEngine (the Protocol) by design - they
    live in different modules and Python doesn't care, but whatever
    wires this into agent.py needs to import one of them under an alias
    to avoid shadowing.

  - failure_mode (FailureMode.FAIL_CLOSED by default): governs what an
    *unexpected internal* error (store unreachable, etc.) becomes - not
    what a normal policy decision is. FAIL_CLOSED denies; FAIL_OPEN
    allows through and logs at CRITICAL every time it fires, since a
    guardrail layer silently disabling itself during an outage is a
    severe operational event, not a routine one. See FailureMode below.

  - Decision-then-log, strictly separated: evaluate() and check_budget()
    fully finalize `decision` (success or internal-failure path) before
    ever touching the store's audit log. _log_safely() is bounded by
    log_timeout_seconds and swallows its own failures - a logging
    problem can never change a decision that was already made. (An
    earlier version of this file had the log write inside the same
    try/except that handles real policy failures, which meant a logging
    timeout during a perfectly good ALLOW could get silently
    miscategorized as an engine failure and turned into a denial.)
    Logging is bounded, not fire-and-forget (no asyncio.create_task):
    PolicyStore's contract preserves log insertion order, and a detached
    background task has no guaranteed completion order relative to
    others under real concurrency - a bounded await keeps that guarantee
    intact while still capping how long a struggling store can hold up
    the return.

No caching of rules anywhere in this class: store.list_rules() is called
fresh on every evaluate(), per the explicit "no caching inside
PolicyEngine" requirement - rule changes from the dashboard take effect
on the very next tool call, with no invalidation logic needed because
there's nothing cached to invalidate.
"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any

from .approvals import ApprovalManager
from .models import (
    ApprovalStatus,
    BudgetState,
    DecisionOutcome,
    PolicyDecision,
    PolicyDecisionLog,
    UsageLike,
    _utcnow,
)
from .rules import RuleEvaluationResult, RuleEvaluator
from .store import PolicyStore

logger = logging.getLogger(__name__)

# Reserved pseudo tool-name for log entries produced by check_budget(),
# which isn't about any one tool call - it runs once per LLM turn,
# before any of that turn's tool calls are known to be permitted. Kept
# as an explicit sentinel (not "") so it reads unambiguously in the
# dashboard's conversation-log view rather than looking like a logging bug.
_BUDGET_CHECK_TOOL_NAME = "__budget_check__"


class FailureMode(Enum):
    """How PolicyEngine behaves when it fails internally (store
    unreachable, an unexpected exception anywhere in evaluate()/
    check_budget()) - distinct from a normal policy decision like BLOCK
    or REJECTED, which is the engine working correctly and saying no.

    FAIL_CLOSED (default, and what this project ships with): an internal
    error denies the call. The cost is availability - a broken store
    blocks every tool call, including ones that would've been fine - but
    that's the correct trade for a guardrail layer: an error in the
    thing enforcing "never allow delete_file" should not silently become
    "allow everything".

    FAIL_OPEN: an internal error allows the call through instead. A
    legitimate choice for some deployments that prioritize availability
    over enforcement when the guardrail itself (not the underlying tool)
    is what's unhealthy - but it means a store outage silently disables
    every guardrail until it recovers. Every resolution under FAIL_OPEN
    is logged at CRITICAL (see PolicyEngine._handle_engine_failure)
    specifically so that risk is loud, never quiet.
    """
    FAIL_CLOSED = "fail_closed"
    FAIL_OPEN = "fail_open"


class PolicyEngine:
    """Implements the evaluate()/check_budget() contract
    backend.agent.tool_loop.PolicyEngine (the Protocol) expects.
    Constructed with its collaborators injected - no global state, no
    singleton.
    """

    def __init__(
        self,
        store: PolicyStore,
        rule_evaluator: RuleEvaluator | None = None,
        approval_manager: ApprovalManager | None = None,
        failure_mode: FailureMode = FailureMode.FAIL_CLOSED,
        log_timeout_seconds: float = 2.0,
    ):
        self.store = store
        self.rules = rule_evaluator or RuleEvaluator()
        # Defaulted from the same store rather than requiring a second
        # constructor argument every caller has to remember to pass -
        # ApprovalManager's only dependency is the store anyway.
        self.approvals = approval_manager or ApprovalManager(store)
        self.failure_mode = failure_mode
        self.log_timeout_seconds = log_timeout_seconds

    # ------------------------------------------------------------------
    # Tool permission
    # ------------------------------------------------------------------

    async def evaluate(
        self,
        *,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> PolicyDecision:
        started = time.perf_counter()
        rewritten_arguments: dict[str, Any] | None = None

        try:
            rules = await self.store.list_rules()
            result = self.rules.evaluate(tool_name, arguments, rules)
            rewritten_arguments = result.rewritten_arguments

            if result.decision_outcome is DecisionOutcome.PENDING_APPROVAL:
                decision = await self._resolve_approval(
                    conversation_id, tool_name, arguments, result
                )
            else:
                decision = PolicyDecision(
                    allowed=result.decision_outcome
                    in (DecisionOutcome.ALLOWED, DecisionOutcome.REWRITTEN),
                    outcome=result.decision_outcome,
                    reason=result.reason,
                    arguments=result.effective_arguments(arguments),
                    matched_rule_id=result.matched_rule.id if result.matched_rule else None,
                )
        except Exception as exc:
            decision = await self._handle_engine_failure(exc)

        await self._log_safely(
            conversation_id=conversation_id,
            tool_name=tool_name,
            arguments=arguments,
            decision=decision,
            started_at=started,
            rewritten_arguments=rewritten_arguments,
        )
        return decision

    async def _resolve_approval(
        self,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: RuleEvaluationResult,
    ) -> PolicyDecision:
        """Owns the entire approval wait, per tool_loop.PolicyEngine's
        contract - ToolLoop only ever sees the terminal PolicyDecision
        this returns, never a "pending" state. Exceptions raised here
        propagate to evaluate()'s try/except, same as any other internal
        failure - there's no separate failure posture for the approval
        path specifically."""

        matched_rule = result.matched_rule
        if matched_rule is None:
            # Impossible by RuleEvaluator's own contract (PENDING_APPROVAL
            # is never returned without a matched_rule) - raised, not
            # asserted, so it's caught by evaluate()'s failure handling
            # even if Python ever runs with assertions stripped.
            raise AssertionError("PENDING_APPROVAL with no matched_rule")

        effective_arguments = result.effective_arguments(arguments)

        approval = await self.approvals.submit_request(
            conversation_id=conversation_id,
            tool_name=tool_name,
            arguments=effective_arguments,
            matched_rule_id=matched_rule.id,
            timeout_seconds=matched_rule.approval_timeout_seconds,
        )
        resolved = await self.approvals.wait_for_resolution(approval.id)

        if resolved.status is ApprovalStatus.APPROVED:
            return PolicyDecision(
                allowed=True,
                outcome=DecisionOutcome.APPROVED,
                reason=resolved.resolution_reason,
                arguments=effective_arguments,
                matched_rule_id=matched_rule.id,
            )

        if resolved.status is ApprovalStatus.REJECTED:
            return PolicyDecision(
                allowed=False,
                outcome=DecisionOutcome.REJECTED,
                reason=resolved.resolution_reason or f"rejected by approver ({matched_rule.name})",
                matched_rule_id=matched_rule.id,
            )

        # TIMED_OUT - the approver-offline case: denied with a clear
        # reason, never a hang.
        return PolicyDecision(
            allowed=False,
            outcome=DecisionOutcome.APPROVAL_TIMED_OUT,
            reason=resolved.resolution_reason or "approval window expired with no response",
            matched_rule_id=matched_rule.id,
        )

    # ------------------------------------------------------------------
    # Token budget
    # ------------------------------------------------------------------

    async def check_budget(
        self,
        *,
        conversation_id: str,
        usage: UsageLike,
    ) -> PolicyDecision:
        """usage must be this turn's incremental usage (one LLM call),
        never a running total - this method IS the running total's owner."""

        started = time.perf_counter()
        log_arguments = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}

        try:
            ceiling = await self.store.get_budget(conversation_id)
            previous_state = await self.store.get_budget_state(conversation_id)

            updated_state = BudgetState(
                conversation_id=conversation_id,
                input_tokens=previous_state.input_tokens + usage.input_tokens,
                output_tokens=previous_state.output_tokens + usage.output_tokens,
            )
            # Persisted unconditionally: the tokens were already spent
            # calling the LLM regardless of what's decided below - the
            # running total has to reflect that reality even on the call
            # that pushes the conversation over its ceiling.
            await self.store.save_budget_state(updated_state)

            if updated_state.total_tokens > ceiling.max_tokens:
                decision = PolicyDecision(
                    allowed=False,
                    outcome=DecisionOutcome.BUDGET_EXCEEDED,
                    reason=(
                        f"conversation token budget exceeded: "
                        f"{updated_state.total_tokens}/{ceiling.max_tokens} tokens used"
                    ),
                )
            else:
                decision = PolicyDecision(allowed=True, outcome=DecisionOutcome.ALLOWED)
        except Exception as exc:
            decision = await self._handle_engine_failure(exc)

        await self._log_safely(
            conversation_id=conversation_id,
            tool_name=_BUDGET_CHECK_TOOL_NAME,
            arguments=log_arguments,
            decision=decision,
            started_at=started,
        )
        return decision

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    # async def _handle_engine_failure(self, exc: Exception) -> PolicyDecision:
    #     """Single point deciding what an unexpected internal failure
    #     becomes, based on self.failure_mode. Never raises, and never
    #     itself writes to PolicyDecisionLog - the resulting decision is
    #     logged by the caller via _log_safely exactly like any other
    #     decision, so it shows up in the dashboard the same way.

    #     A real logging.* call (not PolicyDecisionLog) happens here
    #     regardless of failure_mode: "the policy engine itself just
    #     broke" deserves an immediate operational signal independent of
    #     whether the dashboard's audit-log write later also succeeds.
    #     """
    #     if self.failure_mode is FailureMode.FAIL_OPEN:
    #         logger.critical(
    #             "PolicyEngine failed OPEN due to an internal error - "
    #             "guardrails were bypassed for this call: %s", exc, exc_info=True,
    #         )
    #         return PolicyDecision(
    #             allowed=True,
    #             outcome=DecisionOutcome.FAILED_OPEN,
    #             reason=f"policy engine error, configured to fail OPEN: {exc}",
    #         )

    #     logger.error("PolicyEngine failed CLOSED due to an internal error: %s", exc, exc_info=True)
    #     return PolicyDecision(
    #         allowed=False,
    #         outcome=DecisionOutcome.FAILED_CLOSED,
    #         reason=f"policy engine error, failing closed: {exc}",
    #     )
    # backend/policy/engine.py — _handle_engine_failure, revised

    async def _handle_engine_failure(self, exc: Exception) -> PolicyDecision:
        """Single point deciding what an unexpected internal failure
        becomes, based on self.failure_mode. Never raises, and never
        itself writes to PolicyDecisionLog - the resulting decision is
        logged by the caller via _log_safely exactly like any other
        decision, so it shows up in the dashboard the same way, tagged
        via engine_failure rather than a distinct outcome value (engine
        health and policy outcome are orthogonal - see models.py).

        A real logging.* call happens here regardless of failure_mode:
        "the policy engine itself just broke" deserves an immediate
        operational signal independent of whether the dashboard's audit-
        log write later also succeeds.
        """
        if self.failure_mode is FailureMode.FAIL_OPEN:
            logger.critical(
                "PolicyEngine failed OPEN due to an internal error - "
                "guardrails were bypassed for this call: %s", exc, exc_info=True,
            )
            return PolicyDecision(
                allowed=True,
                outcome=DecisionOutcome.ALLOWED,
                reason=f"policy engine error, configured to fail OPEN: {exc}",
                engine_failure=True,
            )

        logger.error("PolicyEngine failed CLOSED due to an internal error: %s", exc, exc_info=True)
        return PolicyDecision(
            allowed=False,
            outcome=DecisionOutcome.BLOCKED,
            reason=f"policy engine error, failing closed: {exc}",
            engine_failure=True,
        )
    async def _log_safely(
        self,
        *,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        decision: PolicyDecision,
        started_at: float,
        rewritten_arguments: dict[str, Any] | None = None,
    ) -> None:
        """Writes the structured PolicyDecisionLog entry for a decision
        that has already been finalized. Bounded by log_timeout_seconds
        and never raises - see module docstring for why this is bounded
        rather than fire-and-forget, and why it's structurally separated
        from decision-making rather than nested inside it."""
        try:
            await asyncio.wait_for(
                self.store.append_log(
                    PolicyDecisionLog(
                        conversation_id=conversation_id,
                        tool_name=tool_name,
                        arguments=arguments,
                        outcome=decision.outcome or DecisionOutcome.BLOCKED,
                        timestamp=_utcnow(),
                        execution_time_ms=(time.perf_counter() - started_at) * 1000,
                        rewritten_arguments=rewritten_arguments,
                        reason=decision.reason,
                        matched_rule_id=decision.matched_rule_id,
                        engine_failure=decision.engine_failure,
                    )
                ),
                timeout=self.log_timeout_seconds,
            )
        except Exception:
            logger.warning(
                "Failed to write policy decision log (conversation_id=%s, tool_name=%s)",
                conversation_id, tool_name, exc_info=True,
            )