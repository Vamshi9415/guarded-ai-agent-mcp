# backend/api/routers/budgets.py
"""Budget management routes for the FastAPI admin backend."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_policy_store
from backend.api.schemas import (
    BudgetResponse,
    BudgetStateResponse,
    BudgetUpdate,
    to_budget_response,
    to_budget_state_response,
)
from backend.policy.models import ConversationBudget
from backend.policy.store import PolicyStore

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get("/default", response_model=BudgetResponse)
async def get_default_budget(
    store: PolicyStore = Depends(get_policy_store),
) -> BudgetResponse:
    """Returns the current default conversation budget."""
    budget = await store.get_budget("__default__")
    return to_budget_response(
        ConversationBudget(
            conversation_id=None,
            max_tokens=budget.max_tokens,
        )
    )


@router.put("/default", response_model=BudgetResponse)
async def set_default_budget(
    payload: BudgetUpdate,
    store: PolicyStore = Depends(get_policy_store),
) -> BudgetResponse:
    """Sets the global default budget used when a conversation has no override."""
    budget = await store.set_budget(
        ConversationBudget(
            conversation_id=None,
            max_tokens=payload.max_tokens,
        )
    )
    return to_budget_response(budget)


@router.get("/{conversation_id}", response_model=BudgetResponse)
async def get_conversation_budget(
    conversation_id: str,
    store: PolicyStore = Depends(get_policy_store),
) -> BudgetResponse:
    """Returns the effective budget for one conversation."""
    budget = await store.get_budget(conversation_id)
    return to_budget_response(budget)


@router.put("/{conversation_id}", response_model=BudgetResponse)
async def set_conversation_budget(
    conversation_id: str,
    payload: BudgetUpdate,
    store: PolicyStore = Depends(get_policy_store),
) -> BudgetResponse:
    """Sets or replaces a budget override for one conversation."""
    budget = await store.set_budget(
        ConversationBudget(
            conversation_id=conversation_id,
            max_tokens=payload.max_tokens,
        )
    )
    return to_budget_response(budget)


@router.get("/{conversation_id}/state", response_model=BudgetStateResponse)
async def get_conversation_budget_state(
    conversation_id: str,
    store: PolicyStore = Depends(get_policy_store),
) -> BudgetStateResponse:
    """Returns recorded token usage for one conversation."""
    state = await store.get_budget_state(conversation_id)
    return to_budget_state_response(state)
