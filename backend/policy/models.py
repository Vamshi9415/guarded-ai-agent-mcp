# backend/policy/models.py
"""
Data models for the Policy Engine.

Pure data: dataclasses, enums, and one tiny structural Protocol used at
the boundary with the agent's tool-use loop. No matching, evaluation,
persistence, or approval-waiting logic lives here - that's rules.py,
store.py, approvals.py, and engine.py respectively.

Independence note: nothing in backend/policy/* imports from backend/agent
or backend/llm. backend.agent.tool_loop defines its own PolicyDecision
dataclass and PolicyEngine Protocol as the contract it depends on.
PolicyDecision below is a *separate* class with identical core field
names (allowed, reason, arguments) so the two interchange at the call
boundary through plain attribute access - no shared base class, no
cross-package import, in either direction. This is deliberate: it lets
this class grow extra fields (matched_rule_id, outcome, ...) the way it
just did, without ever requiring a change to agent/tool_loop.py. UsageLike
exists for the same reason on the budget side.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4


def _utcnow() -> datetime:
    """Single source of truth for 'now' across every model below, so every
    timestamp in this package is timezone-aware and consistently UTC."""
    return datetime.now(timezone.utc)


def _new_id() -> str:
    """UUID4, as a plain string. Kept as str (not uuid.UUID) so every
    model here round-trips through json.dumps() with no custom encoder -
    these get sent to the dashboard and, later, a real DB, unchanged."""
    return str(uuid4())


# ----------------------------------------------------------------------
# Structural contract shared with backend.agent.tool_loop, duplicated by
# field-shape (not by import) to keep this package independent. See
# module docstring for why this is the deliberate choice, not a gap.
# ----------------------------------------------------------------------

@runtime_checkable
class UsageLike(Protocol):
    """Anything with these two attributes works as the `usage` argument to
    PolicyEngine.check_budget() - in practice always a real
    backend.llm.base.Usage instance, but this package never needs to
    import that type to use it."""
    input_tokens: int
    output_tokens: int

class DecisionOutcome(Enum):
    """Richer than a plain allowed/denied bool - drives both the
    dashboard's conversation-log view and PolicyDecision.outcome. Should
    stay consistent with PolicyDecision.allowed (True for ALLOWED,
    REWRITTEN, APPROVED; False otherwise), but engine.py sets both
    explicitly rather than deriving one from the other.

    PENDING_APPROVAL is transient and internal to the policy package: it's
    what rules.py returns the instant a REQUIRE_APPROVAL rule matches,
    before any human has acted. engine.py is responsible for resolving it
    into a terminal outcome (APPROVED / REJECTED / APPROVAL_TIMED_OUT)
    before anything is returned to ToolLoop - ToolLoop should never see
    PENDING_APPROVAL on a PolicyDecision it receives.
    
    """
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REWRITTEN = "rewritten"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPROVAL_TIMED_OUT = "approval_timed_out"
    BUDGET_EXCEEDED = "budget_exceeded"    


@dataclass(kw_only=True)
class PolicyDecision:
    """Returned by PolicyEngine.evaluate() and PolicyEngine.check_budget().

    `allowed`, `reason`, `arguments` deliberately match
    backend.agent.tool_loop.PolicyDecision's field names exactly - that's
    the whole interchange mechanism (see module docstring). `outcome` and
    `matched_rule_id` are extra context ToolLoop simply never reads;
    engine.py uses them to build PolicyDecisionLog entries without a
    second lookup.
    
    engine_failure marks that this decision resulted from the policy
    engine itself erroring (store unreachable, unexpected exception),
    not from a rule, budget, or approval actually being evaluated.
    Orthogonal to outcome: a FAIL_CLOSED failure sets
    outcome=BLOCKED, engine_failure=True - functionally indistinguishable
    from a real BLOCK rule to ToolLoop (both just deny the call), but
    distinguishable in the audit log for anyone who needs to tell "a
    rule said no" apart from "the engine was broken when this was
    decided".
    """
    allowed: bool
    outcome: DecisionOutcome | None = None
    reason: str | None = None
    arguments: dict[str, Any] | None = None
    matched_rule_id: str | None = None
    engine_failure: bool = False  # NEW

# ----------------------------------------------------------------------
# Rule matching and action
# ----------------------------------------------------------------------

class RuleType(Enum):
    """How a PolicyRule's `tool_pattern` is interpreted against an
    incoming tool name. Orthogonal to RuleAction - this answers "does
    this rule apply here?", not "what happens if it does?"."""
    EXACT = "exact"
    GLOB = "glob"
    REGEX = "regex"


class RuleAction(Enum):
    """What happens when a rule's pattern matches the tool being called."""
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


class RuleScope(Enum):
    """Intended breadth of a rule's effect. NOT YET ENFORCED: rules.py's
    matcher (next file) only reads tool_pattern for now, so a rule with
    scope=CONVERSATION or USER currently behaves identically to GLOBAL.
    Present so the dashboard schema and PolicyRule don't need a breaking
    change later - it's an honest placeholder, not a working feature."""
    GLOBAL = "global"
    CONVERSATION = "conversation"
    USER = "user"


class ConstraintType(Enum):
    """Kinds of per-argument checks a rule can attach. Expected shape of
    ArgumentConstraint.value per type:
      PATH_PREFIX     -> str, required path prefix, e.g. "/sandbox/"
      REGEX           -> str, a regular expression the argument must match
      ALLOWED_VALUES  -> list[Any], the closed set of acceptable values
      MAX_LENGTH      -> int, maximum length of a string/sequence argument
      NUMERIC_RANGE   -> tuple[float, float], inclusive (min, max)
    """
    PATH_PREFIX = "path_prefix"
    REGEX = "regex"
    ALLOWED_VALUES = "allowed_values"
    MAX_LENGTH = "max_length"
    NUMERIC_RANGE = "numeric_range"


@dataclass(kw_only=True)
class ArgumentConstraint:
    """One constraint on a single named argument of a matched tool call.

    allow_rewrite grants *permission* to auto-correct a violation instead
    of blocking outright - it is not the correction itself. What
    "corrected" means is computed procedurally in rules.py from `value`
    for PATH_PREFIX (force/normalize the prefix), MAX_LENGTH (truncate),
    and NUMERIC_RANGE (clamp to the nearest bound) - none of those need a
    stored replacement. ALLOWED_VALUES is the one exception: there's no
    algorithmic "closest" member of an arbitrary set, so rewrite_value
    supplies the explicit fallback to use. rewrite_value is ignored for
    every other constraint_type. REGEX violations have no well-defined
    correction at all and should always block regardless of allow_rewrite.
    """
    field: str
    constraint_type: ConstraintType
    value: Any
    allow_rewrite: bool = False
    rewrite_value: Any | None = None
    description: str | None = None


@dataclass(kw_only=True)
class PolicyRule:
    """One configurable guardrail - the unit the dashboard creates, edits,
    toggles, and reorders by priority. Pure data: no matching or
    evaluation logic lives on this class (see rules.py).

    Conflict resolution across multiple matching rules is by `priority`
    as a plain integer comparison - deterministic, and simple enough for
    the dashboard to show and let an admin reorder directly with no
    hidden tie-breaking to explain.
    """
    name: str
    action: RuleAction
    tool_pattern: str
    id: str = field(default_factory=_new_id)
    rule_type: RuleType = RuleType.GLOB
    priority: int = 0  # Higher value wins on conflict.
    enabled: bool = True
    constraints: list[ArgumentConstraint] = field(default_factory=list)
    approval_timeout_seconds: int = 300
    reason: str | None = None
    description: str | None = None
    scope: RuleScope = RuleScope.GLOBAL          # see RuleScope - not yet enforced
    scope_id: str | None = None                  # conversation_id/user_id when scope != GLOBAL
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)


# ----------------------------------------------------------------------
# Human approval
# ----------------------------------------------------------------------

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


@dataclass(kw_only=True)
class ApprovalRequest:
    """One pending-or-resolved human-approval gate, created when a
    REQUIRE_APPROVAL rule matches. The dashboard reads/writes these
    through PolicyStore; PolicyEngine.evaluate() blocks on resolution via
    approvals.py, but never holds approval state itself.

    expires_at is computed once at creation time (created_at + the
    matched rule's approval_timeout_seconds) and stored directly, rather
    than recomputed from created_at + a timeout on every poll.
    """
    conversation_id: str
    tool_name: str
    arguments: dict[str, Any]
    matched_rule_id: str
    expires_at: datetime
    id: str = field(default_factory=_new_id)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_reason: str | None = None


# ----------------------------------------------------------------------
# Token budget
# ----------------------------------------------------------------------

DEFAULT_MAX_TOKENS_PER_CONVERSATION = 20_000


@dataclass(kw_only=True)
class ConversationBudget:
    """A configured token ceiling, as set via the dashboard.
    conversation_id=None marks the default ceiling applied to any
    conversation with no specific override."""
    max_tokens: int = DEFAULT_MAX_TOKENS_PER_CONVERSATION
    conversation_id: str | None = None


@dataclass(kw_only=True)
class BudgetState:
    """Runtime, mutable record of how much of its budget a conversation
    has actually consumed. Owned and updated exclusively by
    PolicyEngine/PolicyStore - ToolLoop never constructs or reads this
    directly, only the PolicyDecision a check_budget() call returns.

    input_tokens/output_tokens (not "prompt/completion") to stay
    consistent with UsageLike and backend.llm.base.Usage's vocabulary
    rather than introduce a third naming convention. total_tokens is
    computed, not stored, so it can't drift out of sync with the two
    counters that actually get incremented.

    Must be incremented by the *incremental* usage of each LLM call
    (i.e. response.usage from a single generate() call), never by a
    running total computed upstream - that running total is what
    BudgetState itself is for. ToolLoop currently passes a pre-summed
    total, which double-counts; that gets fixed when engine.py wires in.
    """
    conversation_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    last_updated: datetime = field(default_factory=_utcnow)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ----------------------------------------------------------------------
# Structured logging
# ----------------------------------------------------------------------

@dataclass(kw_only=True)
class PolicyDecisionLog:
    """One structured audit record, written by PolicyEngine after every
    evaluate()/check_budget() call - what the dashboard's conversation-log
    view reads from PolicyStore. Intentionally richer than the
    PolicyDecision returned to ToolLoop.

    rewritten_arguments is kept separate from (not overwriting)
    `arguments` so the log preserves both the original call and what
    actually got executed - losing either half breaks auditability for
    exactly the case this exists to cover (e.g. a path-traversal attempt
    that got silently corrected rather than blocked).
    
    engine_failure mirrors PolicyDecision.engine_failure - lets the
    dashboard's conversation-log view filter "engine health events"
    separately from ordinary rule decisions without needing to inspect
    `reason` text to tell them apart.
    """
    conversation_id: str
    tool_name: str
    arguments: dict[str, Any]
    outcome: DecisionOutcome
    timestamp: datetime
    execution_time_ms: float
    rewritten_arguments: dict[str, Any] | None = None
    reason: str | None = None
    matched_rule_id: str | None = None
    engine_failure: bool = False  # NEW