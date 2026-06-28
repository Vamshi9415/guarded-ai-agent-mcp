# backend/api/schemas.py
"""Pydantic schemas for the FastAPI admin backend."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from types import UnionType
from typing import Any
from typing import get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field
from pydantic import model_validator

from backend.policy.models import (
    ApprovalRequest,
    ApprovalStatus,
    ArgumentConstraint,
    BudgetState,
    ConstraintType,
    ConversationBudget,
    DecisionOutcome,
    PolicyDecisionLog,
    PolicyRule,
    RuleAction,
    RuleScope,
    RuleType,
)
from backend.mcp.models import RegisteredTool


class APIModel(BaseModel):
    """Base API model with shared Pydantic configuration."""

    model_config = ConfigDict(
        use_enum_values=False,
        from_attributes=True,
        json_encoders={Enum: lambda value: value.name},
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_enum_names(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        coerced = dict(data)
        for field_name, field_info in cls.model_fields.items():
            if field_name not in coerced:
                continue

            enum_type = _enum_type_from_annotation(field_info.annotation)
            if enum_type is None:
                continue

            value = coerced[field_name]
            if isinstance(value, str) and value in enum_type.__members__:
                coerced[field_name] = enum_type[value]

        return coerced


def _enum_type_from_annotation(annotation: Any) -> type[Enum] | None:
    origin = get_origin(annotation)
    if origin is None:
        return annotation if isinstance(annotation, type) and issubclass(annotation, Enum) else None

    if origin in {tuple, list, set, frozenset, dict}:
        return None

    if origin is UnionType or str(origin) == "typing.Union":
        for arg in get_args(annotation):
            if isinstance(arg, type) and issubclass(arg, Enum):
                return arg

    return None


class ArgumentConstraintPayload(APIModel):
    """Serialized argument constraint payload."""

    field: str
    constraint_type: ConstraintType
    value: Any
    allow_rewrite: bool = False
    rewrite_value: Any | None = None
    description: str | None = None


class RuleCreate(APIModel):
    """Request body for creating a policy rule."""

    name: str = Field(min_length=1)
    action: RuleAction
    tool_pattern: str = Field(min_length=1)
    rule_type: RuleType = RuleType.GLOB
    priority: int = 0
    enabled: bool = True
    constraints: list[ArgumentConstraintPayload] = Field(default_factory=list)
    approval_timeout_seconds: int = Field(default=300, gt=0)
    reason: str | None = None
    description: str | None = None
    scope: RuleScope = RuleScope.GLOBAL
    scope_id: str | None = None


class RuleUpdate(APIModel):
    """Request body for replacing an existing policy rule."""

    name: str = Field(min_length=1)
    action: RuleAction
    tool_pattern: str = Field(min_length=1)
    rule_type: RuleType = RuleType.GLOB
    priority: int = 0
    enabled: bool = True
    constraints: list[ArgumentConstraintPayload] = Field(default_factory=list)
    approval_timeout_seconds: int = Field(default=300, gt=0)
    reason: str | None = None
    description: str | None = None
    scope: RuleScope = RuleScope.GLOBAL
    scope_id: str | None = None


# BudgetSetRequest kept as an alias so budgets.py doesn't break if old name slips in anywhere.
# The canonical name going forward is BudgetUpdate.
class BudgetUpdate(APIModel):
    """Request body for updating a conversation budget."""

    max_tokens: int = Field(gt=0)


# Backward-compatible alias — remove once all callers use BudgetUpdate.
BudgetSetRequest = BudgetUpdate


class ApprovalDecision(APIModel):
    """Request body for resolving an approval.

    The field is named `resolved_by` to match ApprovalManager.approve() /
    ApprovalManager.reject() parameter names exactly, avoiding the kwarg
    mismatch that existed when it was called `approver`.
    """

    resolved_by: str
    reason: str | None = None


class RuleResponse(APIModel):
    """Serialized policy rule."""

    id: str
    name: str
    action: RuleAction
    tool_pattern: str
    rule_type: RuleType
    priority: int
    enabled: bool
    constraints: list[ArgumentConstraintPayload]
    approval_timeout_seconds: int
    reason: str | None
    description: str | None
    scope: RuleScope
    scope_id: str | None
    created_at: datetime
    updated_at: datetime


class ToolResponse(APIModel):
    """Serialized MCP tool metadata for policy authoring."""

    name: str
    description: str | None = None
    server_name: str


class ApprovalResponse(APIModel):
    """Serialized approval request."""

    id: str
    conversation_id: str
    tool_name: str
    arguments: dict[str, Any]
    matched_rule_id: str
    expires_at: datetime
    status: ApprovalStatus
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_reason: str | None


class BudgetResponse(APIModel):
    """Serialized configured budget ceiling."""

    conversation_id: str | None
    max_tokens: int


class BudgetStateResponse(APIModel):
    """Serialized runtime budget usage state."""

    conversation_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    last_updated: datetime


class LogResponse(APIModel):
    """Serialized policy decision log entry."""

    conversation_id: str
    tool_name: str
    arguments: dict[str, Any]
    outcome: DecisionOutcome
    timestamp: datetime
    execution_time_ms: float
    rewritten_arguments: dict[str, Any] | None
    reason: str | None
    matched_rule_id: str | None
    engine_failure: bool = False


class HealthResponse(APIModel):
    """Health endpoint response payload."""

    status: str
    rules: int
    pending_approvals: int
    version: str
    storage_backend: str = "mongo"
    storage_ready: bool = True


def to_argument_constraint(payload: ArgumentConstraintPayload) -> ArgumentConstraint:
    """Converts an API payload into a policy-layer argument constraint."""
    return ArgumentConstraint(
        field=payload.field,
        constraint_type=payload.constraint_type,
        value=payload.value,
        allow_rewrite=payload.allow_rewrite,
        rewrite_value=payload.rewrite_value,
        description=payload.description,
    )


def to_rule_response(rule: PolicyRule) -> RuleResponse:
    """Converts a PolicyRule dataclass into a response model."""
    return RuleResponse.model_validate(rule)


def to_tool_response(tool: RegisteredTool) -> ToolResponse:
    """Converts a discovered MCP tool into a response model."""
    return ToolResponse(
        name=tool.name,
        description=tool.description,
        server_name=tool.server_name,
    )


def to_approval_response(approval: ApprovalRequest) -> ApprovalResponse:
    """Converts an ApprovalRequest dataclass into a response model."""
    return ApprovalResponse.model_validate(approval)


def to_budget_response(budget: ConversationBudget) -> BudgetResponse:
    """Converts a ConversationBudget dataclass into a response model."""
    return BudgetResponse.model_validate(budget)


def to_budget_state_response(state: BudgetState) -> BudgetStateResponse:
    """Converts a BudgetState dataclass into a response model."""
    return BudgetStateResponse(
        conversation_id=state.conversation_id,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
        total_tokens=state.total_tokens,
        last_updated=state.last_updated,
    )


def to_log_response(log: PolicyDecisionLog) -> LogResponse:
    """Converts a PolicyDecisionLog dataclass into a response model."""
    return LogResponse.model_validate(log)
