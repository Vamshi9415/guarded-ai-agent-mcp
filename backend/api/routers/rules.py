# backend/api/routers/rules.py
"""Rule management routes for the FastAPI admin backend."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Response, status

from backend.api.dependencies import get_policy_store
from backend.api.schemas import (
    RuleCreate,
    RuleResponse,
    RuleUpdate,
    to_argument_constraint,
    to_rule_response,
)
from backend.policy.models import PolicyRule
from backend.policy.store import PolicyStore

router = APIRouter(prefix="/rules", tags=["Rules"])
logger = logging.getLogger(__name__)


def _new_rule_id() -> str:
    """Generates a fresh UUID string for a new PolicyRule.

    Previously the code used `PolicyRule.__dataclass_fields__["id"].default_factory()`
    which is a fragile internal-dataclass hack. This function is the clean
    replacement: it generates the same kind of ID (UUID4 str) without coupling
    to dataclass internals or requiring a classmethod on PolicyRule itself.
    """
    return str(uuid.uuid4())


def _build_policy_rule(payload: RuleCreate | RuleUpdate, rule_id: str | None = None) -> PolicyRule:
    """Converts an API payload into a policy-layer PolicyRule."""
    return PolicyRule(
        id=rule_id if rule_id is not None else _new_rule_id(),
        name=payload.name,
        action=payload.action,
        tool_pattern=payload.tool_pattern,
        rule_type=payload.rule_type,
        priority=payload.priority,
        enabled=payload.enabled,
        constraints=[to_argument_constraint(item) for item in payload.constraints],
        approval_timeout_seconds=payload.approval_timeout_seconds,
        reason=payload.reason,
        description=payload.description,
        scope=payload.scope,
        scope_id=payload.scope_id,
    )


@router.get("", response_model=list[RuleResponse])
async def list_rules(store: PolicyStore = Depends(get_policy_store)) -> list[RuleResponse]:
    """Returns all policy rules ordered by store-defined precedence."""
    rules = await store.list_rules()
    return [to_rule_response(rule) for rule in rules]


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: RuleCreate,
    store: PolicyStore = Depends(get_policy_store),
) -> RuleResponse:
    """Creates a new policy rule."""
    logger.info(
        "Creating rule name=%s tool_pattern=%s rule_type=%s action=%s priority=%s scope=%s",
        payload.name,
        payload.tool_pattern,
        payload.rule_type,
        payload.action,
        payload.priority,
        payload.scope,
    )
    rule = _build_policy_rule(payload)
    created = await store.create_rule(rule)
    logger.info("Created rule id=%s name=%s", created.id, created.name)
    return to_rule_response(created)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    store: PolicyStore = Depends(get_policy_store),
) -> RuleResponse:
    """Returns one policy rule by id."""
    rule = await store.get_rule(rule_id)
    return to_rule_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    payload: RuleUpdate,
    store: PolicyStore = Depends(get_policy_store),
) -> RuleResponse:
    """Replaces an existing policy rule, preserving its id and created_at."""
    logger.info(
        "Updating rule id=%s name=%s tool_pattern=%s rule_type=%s action=%s priority=%s enabled=%s",
        rule_id,
        payload.name,
        payload.tool_pattern,
        payload.rule_type,
        payload.action,
        payload.priority,
        payload.enabled,
    )
    existing = await store.get_rule(rule_id)
    updated_rule = PolicyRule(
        id=existing.id,
        created_at=existing.created_at,
        updated_at=existing.updated_at,
        name=payload.name,
        action=payload.action,
        tool_pattern=payload.tool_pattern,
        rule_type=payload.rule_type,
        priority=payload.priority,
        enabled=payload.enabled,
        constraints=[to_argument_constraint(item) for item in payload.constraints],
        approval_timeout_seconds=payload.approval_timeout_seconds,
        reason=payload.reason,
        description=payload.description,
        scope=payload.scope,
        scope_id=payload.scope_id,
    )
    updated = await store.update_rule(updated_rule)
    logger.info("Updated rule id=%s name=%s", updated.id, updated.name)
    return to_rule_response(updated)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    store: PolicyStore = Depends(get_policy_store),
) -> Response:
    """Deletes a policy rule."""
    await store.delete_rule(rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{rule_id}/enable", response_model=RuleResponse)
async def enable_rule(
    rule_id: str,
    store: PolicyStore = Depends(get_policy_store),
) -> RuleResponse:
    """Enables a policy rule."""
    rule = await store.enable_rule(rule_id)
    return to_rule_response(rule)


@router.patch("/{rule_id}/disable", response_model=RuleResponse)
async def disable_rule(
    rule_id: str,
    store: PolicyStore = Depends(get_policy_store),
) -> RuleResponse:
    """Disables a policy rule."""
    rule = await store.disable_rule(rule_id)
    return to_rule_response(rule)
