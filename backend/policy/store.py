# backend/policy/store.py
"""
Persistence abstraction for the Policy Engine.

This module owns exactly one concern: storing and retrieving policy data
- rules, approval requests, conversation budgets, and decision logs. It
contains no rule matching, no constraint evaluation, no approval-waiting
logic, no budget *enforcement* (deciding whether a number exceeds a
limit - that's check_budget() in engine.py; this file only ever stores
and returns numbers), no ToolLoop or MCP awareness, and no
dashboard/HTTP code.

PolicyStore is a typing.Protocol, so PolicyEngine depends only on the
four method groups below, structurally - not on this concrete class.
Swapping InMemoryPolicyStore for a Redis- or Postgres-backed
implementation later means writing one new class against this same
Protocol; nothing in engine.py changes. That's also why every method
here is `async def`, even the ones with no internal `await` - a real
network-backed store needs that signature, and the calling convention
(`await store.get_rule(...)`) has to be identical for both.

Concurrency note: "thread-safe" here means safe under concurrent asyncio
tasks on a single event loop, which is what asyncio.Lock actually
provides - it gives no protection against genuine multi-threaded access
from a second OS thread. That distinction matters if this is ever called
from anywhere other than the event loop FastAPI/the agent runs on.

Because this implementation has no internal `await` points inside any
single method body, Python's cooperative scheduling means no other task
can run *in the middle of* one of these methods regardless of locking -
a coroutine only yields control at an `await`, and there isn't one here.
The locks below are kept anyway, scoped to mutations only, for two
reasons: it's the explicit requirement, and it keeps the calling pattern
correct and forward-compatible with a future implementation that *does*
have real internal awaits (actual network I/O), where that interleaving
protection would start to matter for real. Reads are deliberately
lock-free, which is what makes them non-blocking against writers - they
don't need the lock to be correct, only writers serializing against each
other does.

Independence note, consistent with the rest of backend/policy/*: nothing
here imports from backend.agent, backend.llm, or backend.mcp.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from typing import Protocol, runtime_checkable

from .models import (
    ApprovalRequest,
    ApprovalStatus,
    BudgetState,
    ConversationBudget,
    PolicyDecisionLog,
    PolicyRule,
    _utcnow,  # shared internal time source for the whole policy package -
              # imported rather than re-implemented, so "now" means the
              # same thing everywhere in backend/policy/*.
)


def _missing(kind: str, identifier: str) -> KeyError:
    """One consistent message shape for every "not found" case below,
    rather than six slightly different ad hoc f-strings."""
    return KeyError(f"No {kind} with id '{identifier}'")


# ----------------------------------------------------------------------
# PolicyStore - the Protocol PolicyEngine actually depends on
# ----------------------------------------------------------------------


@runtime_checkable
class PolicyStore(Protocol):
    """Persistence contract for all policy data. Four independent
    collections - rules, approvals, budgets, logs - each with its own
    lifecycle and its own locking granularity in any real implementation,
    bundled into one Protocol only because PolicyEngine needs exactly one
    object injected to reach all four.
    """

    # -- Policy rules --------------------------------------------------

    async def create_rule(self, rule: PolicyRule) -> PolicyRule:
        """Persist a new rule. Raises ValueError if a rule with this id
        already exists - create is not upsert; use update_rule for that."""
        ...

    async def update_rule(self, rule: PolicyRule) -> PolicyRule:
        """Replace the stored rule matching rule.id with the object given.
        Every field is trusted as-is *except* updated_at, which the store
        always overwrites with the current time, regardless of what the
        caller set - same convention as enable_rule/disable_rule. Raises
        KeyError if no rule with this id exists."""

    async def delete_rule(self, rule_id: str) -> None:
        """Raises KeyError if no rule with this id exists."""
        ...

    async def get_rule(self, rule_id: str) -> PolicyRule:
        """Raises KeyError if no rule with this id exists."""
        ...

    async def list_rules(self) -> list[PolicyRule]:
        """All rules - enabled and disabled alike, so a dashboard can
        show and re-enable a disabled one - sorted by priority
        descending. Ties are broken by id purely for a stable, repeatable
        listing order; this is display determinism only, not decision
        logic (that's PriorityResolver's job, in rules.py)."""
        ...

    async def enable_rule(self, rule_id: str) -> PolicyRule:
        """Sets enabled=True and stamps updated_at. Raises KeyError if no
        rule with this id exists."""
        ...

    async def disable_rule(self, rule_id: str) -> PolicyRule:
        """Sets enabled=False and stamps updated_at. Raises KeyError if no
        rule with this id exists."""
        ...

    # -- Approval requests ----------------------------------------------

    async def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        """Raises ValueError if an approval with this id already exists."""
        ...

    async def get_approval(self, approval_id: str) -> ApprovalRequest:
        """Raises KeyError if no approval with this id exists."""
        ...

    async def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        """Replace the stored approval matching approval.id with exactly
        the object given - every field, including status and resolved_at,
        trusted as-is. Resolution timing is approvals.py's decision, not
        this store's; it persists whatever it's told. Raises KeyError if
        no approval with this id exists."""
        ...

    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        """Every approval currently status=PENDING, oldest-created first.
        Does not consider expires_at - an entry past its deadline that
        approvals.py hasn't yet resolved to TIMED_OUT still shows up here;
        noticing and resolving that is approvals.py's job, not this
        store's."""
        ...

    # -- Conversation budgets --------------------------------------------

    async def get_budget(self, conversation_id: str) -> ConversationBudget:
        """The effective ceiling for this conversation: a conversation-
        specific override if one was set, else the global default (set
        via set_budget(ConversationBudget(conversation_id=None, ...))),
        else the hardcoded DEFAULT_MAX_TOKENS_PER_CONVERSATION. Never
        raises - every conversation has *some* effective budget, even one
        no admin has ever touched. The returned object's conversation_id
        always equals the one queried, regardless of which underlying
        record (specific or default) actually supplied the number."""
        ...

    async def set_budget(self, budget: ConversationBudget) -> ConversationBudget:
        """Upsert. budget.conversation_id=None sets the global default
        applied to any conversation without its own override."""
        ...

    async def get_budget_state(self, conversation_id: str) -> BudgetState:
        """Cumulative usage so far for this conversation. Never raises
        and never has the side effect of creating a stored entry - a
        conversation with no recorded usage yet gets a fresh, ephemeral
        zeroed BudgetState, not a write."""
        ...

    async def save_budget_state(self, state: BudgetState) -> BudgetState:
        """Upsert, keyed by state.conversation_id. Stamps last_updated to
        the moment of this save, overriding whatever the caller set -
        this is the store's own write, so it owns that timestamp (see
        module docstring)."""
        ...

    # -- Decision logs ----------------------------------------------------

    async def append_log(self, log: PolicyDecisionLog) -> None:
        """Append-only; logs are never mutated after being written."""
        ...

    async def get_logs(self, conversation_id: str | None = None) -> list[PolicyDecisionLog]:
        """All logs in original insertion order, optionally filtered to
        one conversation. conversation_id=None returns every log across
        every conversation."""
        ...

    async def clear_logs(self, conversation_id: str | None = None) -> None:
        """Deletes logs for one conversation, or - with no argument -
        every log this store holds. The no-argument form is a full wipe;
        it exists for completeness as an admin action, not as something
        meant to be called casually."""
        ...


# ----------------------------------------------------------------------
# InMemoryPolicyStore - the only concrete implementation in this file
# ----------------------------------------------------------------------


class InMemoryPolicyStore(PolicyStore):
    """In-process, dict/list-backed PolicyStore. Needs no injected
    dependencies of its own - it holds no external connections - because
    its entire purpose is to *be* injected into PolicyEngine, not to
    depend on anything itself. No module-level state, no singleton: every
    caller constructs and owns its own instance (typically one, created
    once at application startup and handed to PolicyEngine's constructor,
    and to whatever route handlers the dashboard API uses to read/write
    rules - the same instance, so both sides see the same data).

    Every object that crosses this class's boundary - in via a create/
    update/save call, or out via any getter - is deep-copied. Copying
    on the way out is the literal "never expose mutable internal
    collections" requirement; copying on the way in is the same guarantee
    applied to the other direction - without it, a caller mutating the
    PolicyRule object they already called create_rule() with would
    silently corrupt this store's copy too, since both names would still
    point at one object.
    """

    def __init__(self) -> None:
        self._rules: dict[str, PolicyRule] = {}
        self._rules_lock = asyncio.Lock()

        self._approvals: dict[str, ApprovalRequest] = {}
        self._approvals_lock = asyncio.Lock()

        # One lock for both budget dicts: the spec groups "conversation
        # budgets" (ceilings) and "budget state" (consumption) as a
        # single collection, and the two are read/written together often
        # enough in practice that splitting the lock would add
        # complexity without a real concurrency win.
        self._budget_ceilings: dict[str | None, ConversationBudget] = {}
        self._budget_states: dict[str, BudgetState] = {}
        self._budgets_lock = asyncio.Lock()

        self._logs: list[PolicyDecisionLog] = []
        self._logs_lock = asyncio.Lock()

    # -- Policy rules -----------------------------------------------------

    async def create_rule(self, rule: PolicyRule) -> PolicyRule:
        async with self._rules_lock:
            if rule.id in self._rules:
                raise ValueError(f"Rule with id '{rule.id}' already exists")
            stored = deepcopy(rule)
            self._rules[rule.id] = stored
            return deepcopy(stored)

    async def update_rule(self, rule: PolicyRule) -> PolicyRule:
        async with self._rules_lock:
            if rule.id not in self._rules:
                raise _missing("rule", rule.id)
            stored = replace(deepcopy(rule), updated_at=_utcnow())
            self._rules[rule.id] = stored
            return deepcopy(stored)

    async def delete_rule(self, rule_id: str) -> None:
        async with self._rules_lock:
            if rule_id not in self._rules:
                raise _missing("rule", rule_id)
            del self._rules[rule_id]

    async def get_rule(self, rule_id: str) -> PolicyRule:
        rule = self._rules.get(rule_id)  # lock-free: see module docstring
        if rule is None:
            raise _missing("rule", rule_id)
        return deepcopy(rule)

    async def list_rules(self) -> list[PolicyRule]:
        rules = list(self._rules.values())  # lock-free read, snapshot
        rules.sort(key=lambda r: (-r.priority, r.id))
        return [deepcopy(rule) for rule in rules]

    async def enable_rule(self, rule_id: str) -> PolicyRule:
        return await self._set_rule_enabled(rule_id, enabled=True)

    async def disable_rule(self, rule_id: str) -> PolicyRule:
        return await self._set_rule_enabled(rule_id, enabled=False)

    async def _set_rule_enabled(self, rule_id: str, *, enabled: bool) -> PolicyRule:
        async with self._rules_lock:
            existing = self._rules.get(rule_id)
            if existing is None:
                raise _missing("rule", rule_id)
            updated = replace(existing, enabled=enabled, updated_at=_utcnow())
            self._rules[rule_id] = updated
            return deepcopy(updated)

    # -- Approval requests ------------------------------------------------

    async def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        async with self._approvals_lock:
            if approval.id in self._approvals:
                raise ValueError(f"Approval with id '{approval.id}' already exists")
            stored = deepcopy(approval)
            self._approvals[approval.id] = stored
            return deepcopy(stored)

    async def get_approval(self, approval_id: str) -> ApprovalRequest:
        approval = self._approvals.get(approval_id)  # lock-free read
        if approval is None:
            raise _missing("approval", approval_id)
        return deepcopy(approval)

    async def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        async with self._approvals_lock:
            if approval.id not in self._approvals:
                raise _missing("approval", approval.id)
            stored = deepcopy(approval)  # trusted verbatim - see Protocol docstring
            self._approvals[approval.id] = stored
            return deepcopy(stored)

    async def list_pending_approvals(self) -> list[ApprovalRequest]:
        pending = [
            deepcopy(approval) for approval in self._approvals.values()
            if approval.status is ApprovalStatus.PENDING
        ]
        return pending  # dict preserves insertion order -> creation order

    # -- Conversation budgets ----------------------------------------------

    async def get_budget(self, conversation_id: str) -> ConversationBudget:
        specific = self._budget_ceilings.get(conversation_id)  # lock-free
        if specific is not None:
            return replace(specific, conversation_id=conversation_id)

        default = self._budget_ceilings.get(None)
        if default is not None:
            return replace(default, conversation_id=conversation_id)

        return ConversationBudget(conversation_id=conversation_id)

    async def set_budget(self, budget: ConversationBudget) -> ConversationBudget:
        async with self._budgets_lock:
            stored = deepcopy(budget)
            self._budget_ceilings[budget.conversation_id] = stored
            return deepcopy(stored)

    async def get_budget_state(self, conversation_id: str) -> BudgetState:
        state = self._budget_states.get(conversation_id)  # lock-free
        if state is not None:
            return deepcopy(state)
        return BudgetState(conversation_id=conversation_id)  # ephemeral, not stored

    async def save_budget_state(self, state: BudgetState) -> BudgetState:
        async with self._budgets_lock:
            stored = replace(deepcopy(state), last_updated=_utcnow())
            self._budget_states[state.conversation_id] = stored
            return deepcopy(stored)

    # -- Decision logs ------------------------------------------------------

    async def append_log(self, log: PolicyDecisionLog) -> None:
        async with self._logs_lock:
            self._logs.append(deepcopy(log))

    async def get_logs(self, conversation_id: str | None = None) -> list[PolicyDecisionLog]:
        logs = self._logs  # lock-free read, snapshot iteration below
        if conversation_id is not None:
            logs = [log for log in logs if log.conversation_id == conversation_id]
        return [deepcopy(log) for log in logs]

    async def clear_logs(self, conversation_id: str | None = None) -> None:
        async with self._logs_lock:
            if conversation_id is None:
                self._logs.clear()
            else:
                self._logs[:] = [
                    log for log in self._logs if log.conversation_id != conversation_id
                ]