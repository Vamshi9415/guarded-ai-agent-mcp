"""Regression tests for approval reuse in the policy engine."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.policy.approvals import ApprovalManager
from backend.policy.engine import PolicyEngine
from backend.policy.models import DecisionOutcome, PolicyRule, RuleAction, RuleType
from backend.policy.store import InMemoryPolicyStore


def test_same_conversation_reuses_existing_approval() -> None:
    async def scenario() -> None:
        store = InMemoryPolicyStore()
        await store.create_rule(
            PolicyRule(
                name="approve-update-record",
                action=RuleAction.REQUIRE_APPROVAL,
                tool_pattern="update_record",
                rule_type=RuleType.EXACT,
                approval_timeout_seconds=30,
            )
        )

        approvals = ApprovalManager(store)
        engine = PolicyEngine(store, approval_manager=approvals)
        arguments = {"key": "user_1", "role": "Developer"}

        first_task = asyncio.create_task(
            engine.evaluate(
                conversation_id="conv-1",
                tool_name="update_record",
                arguments=arguments,
            )
        )

        pending_id = None
        for _ in range(100):
            pending = await store.list_pending_approvals()
            if pending:
                pending_id = pending[0].id
                break
            await asyncio.sleep(0.01)

        assert pending_id is not None
        await approvals.approve(pending_id, resolved_by="admin", reason="approved once")

        first_decision = await first_task
        assert first_decision.allowed is True
        assert first_decision.outcome is DecisionOutcome.APPROVED

        approvals_before = await store.list_approvals()
        second_decision = await engine.evaluate(
            conversation_id="conv-1",
            tool_name="update_record",
            arguments=arguments,
        )
        approvals_after = await store.list_approvals()

        assert second_decision.allowed is True
        assert second_decision.outcome is DecisionOutcome.APPROVED
        assert len(approvals_before) == 1
        assert len(approvals_after) == 1

    asyncio.run(scenario())