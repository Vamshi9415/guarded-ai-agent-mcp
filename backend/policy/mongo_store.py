"""MongoDB-backed PolicyStore implementation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from enum import Enum
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from .mongo_connection import MongoSettings, create_mongo_client
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    ArgumentConstraint,
    BudgetState,
    ConversationBudget,
    DecisionOutcome,
    PolicyDecisionLog,
    PolicyRule,
    RuleAction,
    RuleScope,
    RuleType,
    ConstraintType,
    _utcnow,
)
from .store import PolicyStore, _missing


def _encode_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if isinstance(value, tuple):
        return [_encode_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode_value(item) for key, item in value.items()}
    return value


def _decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _decode_value(item) for key, item in value.items()}
    return value


def _constraint_to_doc(constraint: ArgumentConstraint) -> dict[str, Any]:
    return {
        "field": constraint.field,
        "constraint_type": constraint.constraint_type.value,
        "value": _encode_value(constraint.value),
        "allow_rewrite": constraint.allow_rewrite,
        "rewrite_value": _encode_value(constraint.rewrite_value),
        "description": constraint.description,
    }


def _constraint_from_doc(doc: dict[str, Any]) -> ArgumentConstraint:
    return ArgumentConstraint(
        field=doc["field"],
        constraint_type=ConstraintType(doc["constraint_type"]),
        value=_decode_value(doc.get("value")),
        allow_rewrite=bool(doc.get("allow_rewrite", False)),
        rewrite_value=_decode_value(doc.get("rewrite_value")),
        description=doc.get("description"),
    )


def _rule_to_doc(rule: PolicyRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "action": rule.action.value,
        "tool_pattern": rule.tool_pattern,
        "rule_type": rule.rule_type.value,
        "priority": rule.priority,
        "enabled": rule.enabled,
        "constraints": [_constraint_to_doc(item) for item in rule.constraints],
        "approval_timeout_seconds": rule.approval_timeout_seconds,
        "reason": rule.reason,
        "description": rule.description,
        "scope": rule.scope.value,
        "scope_id": rule.scope_id,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _rule_from_doc(doc: dict[str, Any]) -> PolicyRule:
    return PolicyRule(
        id=doc["id"],
        name=doc["name"],
        action=RuleAction(doc["action"]),
        tool_pattern=doc["tool_pattern"],
        rule_type=RuleType(doc["rule_type"]),
        priority=int(doc.get("priority", 0)),
        enabled=bool(doc.get("enabled", True)),
        constraints=[_constraint_from_doc(item) for item in doc.get("constraints", [])],
        approval_timeout_seconds=int(doc.get("approval_timeout_seconds", 300)),
        reason=doc.get("reason"),
        description=doc.get("description"),
        scope=RuleScope(doc.get("scope", RuleScope.GLOBAL.value)),
        scope_id=doc.get("scope_id"),
        created_at=doc.get("created_at", _utcnow()),
        updated_at=doc.get("updated_at", _utcnow()),
    )


def _approval_to_doc(approval: ApprovalRequest) -> dict[str, Any]:
    return {
        "id": approval.id,
        "conversation_id": approval.conversation_id,
        "tool_name": approval.tool_name,
        "arguments": _encode_value(approval.arguments),
        "matched_rule_id": approval.matched_rule_id,
        "expires_at": approval.expires_at,
        "status": approval.status.value,
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
        "resolved_by": approval.resolved_by,
        "resolution_reason": approval.resolution_reason,
    }


def _approval_from_doc(doc: dict[str, Any]) -> ApprovalRequest:
    return ApprovalRequest(
        id=doc["id"],
        conversation_id=doc["conversation_id"],
        tool_name=doc["tool_name"],
        arguments=_decode_value(doc.get("arguments", {})),
        matched_rule_id=doc["matched_rule_id"],
        expires_at=doc["expires_at"],
        status=ApprovalStatus(doc.get("status", ApprovalStatus.PENDING.value)),
        created_at=doc.get("created_at", _utcnow()),
        resolved_at=doc.get("resolved_at"),
        resolved_by=doc.get("resolved_by"),
        resolution_reason=doc.get("resolution_reason"),
    )


def _budget_to_doc(budget: ConversationBudget) -> dict[str, Any]:
    return {
        "conversation_id": budget.conversation_id,
        "max_tokens": budget.max_tokens,
    }


def _budget_from_doc(doc: dict[str, Any]) -> ConversationBudget:
    return ConversationBudget(
        conversation_id=doc.get("conversation_id"),
        max_tokens=int(doc.get("max_tokens", 0)),
    )


def _budget_state_to_doc(state: BudgetState) -> dict[str, Any]:
    return {
        "conversation_id": state.conversation_id,
        "input_tokens": state.input_tokens,
        "output_tokens": state.output_tokens,
        "last_updated": state.last_updated,
    }


def _budget_state_from_doc(doc: dict[str, Any]) -> BudgetState:
    return BudgetState(
        conversation_id=doc["conversation_id"],
        input_tokens=int(doc.get("input_tokens", 0)),
        output_tokens=int(doc.get("output_tokens", 0)),
        last_updated=doc.get("last_updated", _utcnow()),
    )


def _log_to_doc(log: PolicyDecisionLog) -> dict[str, Any]:
    return {
        "conversation_id": log.conversation_id,
        "tool_name": log.tool_name,
        "arguments": _encode_value(log.arguments),
        "outcome": log.outcome.value,
        "timestamp": log.timestamp,
        "execution_time_ms": log.execution_time_ms,
        "rewritten_arguments": _encode_value(log.rewritten_arguments),
        "reason": log.reason,
        "matched_rule_id": log.matched_rule_id,
        "engine_failure": log.engine_failure,
    }


def _log_from_doc(doc: dict[str, Any]) -> PolicyDecisionLog:
    return PolicyDecisionLog(
        conversation_id=doc["conversation_id"],
        tool_name=doc["tool_name"],
        arguments=_decode_value(doc.get("arguments", {})),
        outcome=DecisionOutcome(doc["outcome"]),
        timestamp=doc["timestamp"],
        execution_time_ms=float(doc.get("execution_time_ms", 0.0)),
        rewritten_arguments=_decode_value(doc.get("rewritten_arguments")),
        reason=doc.get("reason"),
        matched_rule_id=doc.get("matched_rule_id"),
        engine_failure=bool(doc.get("engine_failure", False)),
    )


class MongoPolicyStore(PolicyStore):
    """MongoDB-backed persistence for policy state."""

    def __init__(self, db_name: str | None = None) -> None:
        self._settings = MongoSettings.from_env()
        self._client = create_mongo_client()
        self._client.admin.command("ping")
        self._db: Database = self._client[db_name or self._settings.db_name]

        self._rules: Collection[dict[str, Any]] = self._db["policy_rules"]
        self._approvals: Collection[dict[str, Any]] = self._db["policy_approvals"]
        self._budget_ceilings: Collection[dict[str, Any]] = self._db["policy_budgets"]
        self._budget_states: Collection[dict[str, Any]] = self._db["policy_budget_states"]
        self._logs: Collection[dict[str, Any]] = self._db["policy_logs"]

        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._rules.create_index([( "id", ASCENDING )], unique=True)
        self._approvals.create_index([( "id", ASCENDING )], unique=True)
        self._approvals.create_index([( "status", ASCENDING ), ("created_at", ASCENDING)])
        self._budget_ceilings.create_index([( "conversation_id", ASCENDING )], unique=True)
        self._budget_states.create_index([( "conversation_id", ASCENDING )], unique=True)
        self._logs.create_index([( "conversation_id", ASCENDING ), ("timestamp", ASCENDING)])

    def close(self) -> None:
        self._client.close()

    async def create_rule(self, rule: PolicyRule) -> PolicyRule:
        doc = _rule_to_doc(rule)
        try:
            self._rules.insert_one(doc)
        except Exception as exc:
            raise ValueError(f"Rule with id '{rule.id}' already exists") from exc
        return _rule_from_doc(doc)

    async def update_rule(self, rule: PolicyRule) -> PolicyRule:
        doc = _rule_to_doc(replace(deepcopy(rule), updated_at=_utcnow()))
        result = self._rules.replace_one({"id": rule.id}, doc)
        if result.matched_count == 0:
            raise _missing("rule", rule.id)
        return _rule_from_doc(doc)

    async def delete_rule(self, rule_id: str) -> None:
        result = self._rules.delete_one({"id": rule_id})
        if result.deleted_count == 0:
            raise _missing("rule", rule_id)

    async def get_rule(self, rule_id: str) -> PolicyRule:
        doc = self._rules.find_one({"id": rule_id}, {"_id": 0})
        if doc is None:
            raise _missing("rule", rule_id)
        return _rule_from_doc(doc)

    async def list_rules(self) -> list[PolicyRule]:
        docs = list(self._rules.find({}, {"_id": 0}).sort([("priority", DESCENDING), ("id", ASCENDING)]))
        return [_rule_from_doc(doc) for doc in docs]

    async def enable_rule(self, rule_id: str) -> PolicyRule:
        return await self._set_rule_enabled(rule_id, enabled=True)

    async def disable_rule(self, rule_id: str) -> PolicyRule:
        return await self._set_rule_enabled(rule_id, enabled=False)

    async def _set_rule_enabled(self, rule_id: str, *, enabled: bool) -> PolicyRule:
        doc = self._rules.find_one({"id": rule_id}, {"_id": 0})
        if doc is None:
            raise _missing("rule", rule_id)
        rule = _rule_from_doc(doc)
        updated = replace(rule, enabled=enabled, updated_at=_utcnow())
        self._rules.replace_one({"id": rule_id}, _rule_to_doc(updated))
        return updated

    async def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        doc = _approval_to_doc(approval)
        try:
            self._approvals.insert_one(doc)
        except Exception as exc:
            raise ValueError(f"Approval with id '{approval.id}' already exists") from exc
        return _approval_from_doc(doc)

    async def get_approval(self, approval_id: str) -> ApprovalRequest:
        doc = self._approvals.find_one({"id": approval_id}, {"_id": 0})
        if doc is None:
            raise _missing("approval", approval_id)
        return _approval_from_doc(doc)

    async def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        doc = _approval_to_doc(deepcopy(approval))
        result = self._approvals.replace_one({"id": approval.id}, doc)
        if result.matched_count == 0:
            raise _missing("approval", approval.id)
        return _approval_from_doc(doc)

    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        docs = list(
            self._approvals.find({"status": ApprovalStatus.PENDING.value}, {"_id": 0}).sort([("created_at", ASCENDING)])
        )
        return [_approval_from_doc(doc) for doc in docs]

    async def list_approvals(self) -> list[ApprovalRequest]:
        docs = list(self._approvals.find({}, {"_id": 0}).sort([("created_at", ASCENDING)]))
        return [_approval_from_doc(doc) for doc in docs]

    async def get_budget(self, conversation_id: str) -> ConversationBudget:
        specific = self._budget_ceilings.find_one({"conversation_id": conversation_id}, {"_id": 0})
        if specific is not None:
            return ConversationBudget(conversation_id=conversation_id, max_tokens=int(specific["max_tokens"]))

        default = self._budget_ceilings.find_one({"conversation_id": None}, {"_id": 0})
        if default is not None:
            return ConversationBudget(conversation_id=conversation_id, max_tokens=int(default["max_tokens"]))

        return ConversationBudget(conversation_id=conversation_id)

    async def set_budget(self, budget: ConversationBudget) -> ConversationBudget:
        doc = _budget_to_doc(deepcopy(budget))
        self._budget_ceilings.replace_one({"conversation_id": budget.conversation_id}, doc, upsert=True)
        return _budget_from_doc(doc)

    async def delete_budget(self, conversation_id: str) -> None:
        result = self._budget_ceilings.delete_one({"conversation_id": conversation_id})
        if result.deleted_count == 0:
            raise _missing("budget", conversation_id)

    async def list_budgets(self) -> list[ConversationBudget]:
        docs = list(self._budget_ceilings.find({}, {"_id": 0}).sort([("conversation_id", ASCENDING)]))
        return [_budget_from_doc(doc) for doc in docs]

    async def get_budget_state(self, conversation_id: str) -> BudgetState:
        doc = self._budget_states.find_one({"conversation_id": conversation_id}, {"_id": 0})
        if doc is not None:
            return _budget_state_from_doc(doc)
        return BudgetState(conversation_id=conversation_id)

    async def save_budget_state(self, state: BudgetState) -> BudgetState:
        stored = replace(deepcopy(state), last_updated=_utcnow())
        self._budget_states.replace_one({"conversation_id": stored.conversation_id}, _budget_state_to_doc(stored), upsert=True)
        return deepcopy(stored)

    async def append_log(self, log: PolicyDecisionLog) -> None:
        self._logs.insert_one(_log_to_doc(log))

    async def get_logs(self, conversation_id: str | None = None) -> list[PolicyDecisionLog]:
        query: dict[str, Any] = {}
        if conversation_id is not None:
            query["conversation_id"] = conversation_id
        docs = list(self._logs.find(query, {"_id": 0}).sort([("timestamp", ASCENDING)]))
        return [_log_from_doc(doc) for doc in docs]

    async def clear_logs(self, conversation_id: str | None = None) -> None:
        query: dict[str, Any] = {}
        if conversation_id is not None:
            query["conversation_id"] = conversation_id
        self._logs.delete_many(query)
