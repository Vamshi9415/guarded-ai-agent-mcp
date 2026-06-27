# backend/policy/rules.py
"""
Pure rule-evaluation logic for the Policy Engine.

Given (tool_name, arguments, list[PolicyRule]), this module decides which
rule applies, whether the call's arguments satisfy that rule's
constraints, and what (if anything) should be rewritten. It has no idea
conversations, token budgets, human approval, persistence, databases, the
dashboard, MCP, or ToolLoop exist. Everything here is deterministic, side
effect free, and fully testable with plain dicts and dataclasses - no
mocks, no async, no I/O.

Composition (each class has exactly one job):

    RuleMatcher         tool_name, rules        -> all rules that apply
    PriorityResolver    matching rules           -> the single winner
    ConstraintEvaluator  arguments, constraints  -> valid / rewritten / blocked
    RuleEvaluator        (facade over the above) -> RuleEvaluationResult
"""
from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any, Callable

from .models import (
    ArgumentConstraint,
    ConstraintType,
    DecisionOutcome,
    PolicyRule,
    RuleAction,
    RuleType,
)

# ----------------------------------------------------------------------
# Shared regex compilation cache - used by RuleMatcher's REGEX matching
# and the REGEX constraint type below. Python's re module already caches
# recently-used patterns internally, but that's an implementation detail,
# not a documented guarantee; this makes the caching explicit and bounds
# it so a long-running engine can't grow it unbounded as dashboard rules
# come and go over time.
# ----------------------------------------------------------------------


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


# ----------------------------------------------------------------------
# RuleMatcher
# ----------------------------------------------------------------------


class RuleMatcher:
    """Determines which rules apply to a given tool name. Pure pattern
    matching only - never ranks results, never picks a winner (that's
    PriorityResolver's job), never inspects arguments.

    A disabled rule (`enabled=False`) is filtered out here rather than
    upstream in RuleEvaluator: "does this rule match" should mean "does
    this rule currently apply", and a toggled-off rule applies to
    nothing, by definition. That's a property of the rule itself, not of
    conversations/budgets/persistence - so it stays in scope for this
    module even though those other concerns explicitly don't.
    """

    def match(self, tool_name: str, rules: Sequence[PolicyRule]) -> list[PolicyRule]:
        return [
            rule for rule in rules
            if rule.enabled and self._matches_pattern(tool_name, rule)
        ]

    @staticmethod
    def _matches_pattern(tool_name: str, rule: PolicyRule) -> bool:
        if rule.rule_type is RuleType.EXACT:
            return tool_name == rule.tool_pattern

        if rule.rule_type is RuleType.GLOB:
            return fnmatch.fnmatch(tool_name, rule.tool_pattern)

        if rule.rule_type is RuleType.REGEX:
            # fullmatch, not search: a pattern meant to select tool names
            # should match the whole name, not merely appear somewhere
            # inside it - "search" would let pattern "record" match
            # delete_record, create_record, and update_record alike,
            # which is rarely what an admin authoring a single-tool block
            # actually wants. Use GLOB ("*record") if that breadth really
            # is the intent.
            return _compile(rule.tool_pattern).fullmatch(tool_name) is not None

        # Defensive: a RuleType added later without a matching arm here
        # fails closed (does not match) rather than raising or silently
        # matching everything.
        return False


# ----------------------------------------------------------------------
# PriorityResolver
# ----------------------------------------------------------------------

_ACTION_PRECEDENCE: dict[RuleAction, int] = {
    RuleAction.BLOCK: 0,
    RuleAction.REQUIRE_APPROVAL: 1,
    RuleAction.ALLOW: 2,
}


class PriorityResolver:
    """Given multiple matching rules, deterministically picks exactly
    one. Operates purely on rule metadata (priority, action, id) - never
    looks at arguments or constraints.
    """

    def resolve(self, matches: Sequence[PolicyRule]) -> PolicyRule | None:
        if not matches:
            return None
        return min(matches, key=self._sort_key)

    @staticmethod
    def _sort_key(rule: PolicyRule) -> tuple[int, int, str]:
        # Sorted ascending, smallest key wins:
        #   1. -priority      -> higher priority sorts first
        #   2. action rank    -> on a priority tie: BLOCK, then
        #                        REQUIRE_APPROVAL, then ALLOW
        #   3. rule.id        -> final, fully deterministic tiebreak
        #
        # rule.id rather than list position is deliberate. Callers may
        # source `rules` from a dict, an unordered store query, or
        # anything else with no guaranteed iteration order. Tiebreaking
        # on an immutable per-rule value means the same set of rules
        # always resolves to the same winner no matter how this
        # particular call happened to order the list - that's what
        # "deterministic" has to mean here, not just "stable for this run".
        return (-rule.priority, _ACTION_PRECEDENCE[rule.action], rule.id)


# ----------------------------------------------------------------------
# ConstraintEvaluator
# ----------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ConstraintResult:
    """Outcome of checking one full arguments dict against a rule's
    constraint list.

    valid=False means at least one constraint was violated and could not
    (or was not permitted to) be rewritten - the call should be blocked.
    valid=True with rewritten=True means every constraint passed, but
    only after substituting rewritten_arguments for the originals.
    """
    valid: bool
    rewritten: bool = False
    rewritten_arguments: dict[str, Any] | None = None
    violation_reason: str | None = None


@dataclass(frozen=True)
class _FieldOutcome:
    """Internal, single-field result. Never leaves this module -
    ConstraintEvaluator aggregates these into a single ConstraintResult.
    new_value is only meaningful when rewritten=True."""
    valid: bool
    rewritten: bool = False
    new_value: Any = None
    violation_reason: str | None = None


def _check_path_prefix(value: Any, constraint: ArgumentConstraint) -> _FieldOutcome:
    """constraint.value is the required prefix, e.g. "/sandbox". Uses
    PurePosixPath throughout - sandbox-style guardrail paths are POSIX
    paths by convention here, regardless of the host OS the agent process
    itself runs on.
    """
    prefix = PurePosixPath(str(constraint.value))
    candidate = PurePosixPath(str(value))

    has_traversal = ".." in candidate.parts

    # Part-wise comparison, not str.startswith(): a naive string check
    # would let "/sandboxevil/x" pass a "/sandbox" prefix check, since
    # "/sandboxevil" *starts with* the text "/sandbox" even though it is
    # not a path "under" it.
    is_under_prefix = (
        not has_traversal
        and candidate.parts[: len(prefix.parts)] == prefix.parts
    )

    if is_under_prefix:
        return _FieldOutcome(valid=True)

    if not constraint.allow_rewrite:
        return _FieldOutcome(
            valid=False,
            violation_reason=f"path '{value}' is not under required prefix '{prefix}'",
        )

    # Drop every ".." and the path's own root/anchor, leaving only the
    # safe relative remainder, then re-root it under the required prefix.
    # This is what makes the rewrite immune to traversal: "../../etc/x"
    # and "/etc/x" both reduce to "etc/x" before being rejoined below.
    safe_parts = [
        part for part in candidate.parts
        if part != ".." and part != candidate.anchor
    ]
    rewritten = (prefix / PurePosixPath(*safe_parts)) if safe_parts else prefix
    return _FieldOutcome(valid=True, rewritten=True, new_value=str(rewritten))


def _check_regex(value: Any, constraint: ArgumentConstraint) -> _FieldOutcome:
    """constraint.value is a regular expression the argument must match
    in full. fullmatch, not search, for the same reason as tool-pattern
    REGEX above - and critically here, search would let
    "/sandbox/" + malicious_suffix slip past any pattern anchored only to
    a safe prefix.

    Per spec, REGEX constraints are never rewritten - there is no general
    way to algorithmically "fix" an arbitrary string into matching an
    arbitrary pattern - so allow_rewrite is ignored entirely for this
    constraint type.
    """
    pattern = str(constraint.value)
    if _compile(pattern).fullmatch(str(value)) is not None:
        return _FieldOutcome(valid=True)

    return _FieldOutcome(
        valid=False,
        violation_reason=f"value '{value}' does not match required pattern '{pattern}'",
    )


def _check_max_length(value: Any, constraint: ArgumentConstraint) -> _FieldOutcome:
    """constraint.value is the maximum length. Works on anything sized -
    strings, lists, tuples. allow_rewrite truncates; without it, anything
    over the limit is a violation."""

    max_length = int(constraint.value)

    try:
        length = len(value)
    except TypeError:
        # Not a sized value (e.g. an int/bool where a string or list was
        # expected). That's a tool-schema mismatch, not something
        # MAX_LENGTH can judge - left for whatever validates the call
        # against its MCP input_schema instead of failing here.
        return _FieldOutcome(valid=True)

    if length <= max_length:
        return _FieldOutcome(valid=True)

    if not constraint.allow_rewrite:
        return _FieldOutcome(
            valid=False,
            violation_reason=f"length {length} exceeds maximum of {max_length}",
        )

    return _FieldOutcome(valid=True, rewritten=True, new_value=value[:max_length])


def _check_allowed_values(value: Any, constraint: ArgumentConstraint) -> _FieldOutcome:
    """constraint.value is the closed list of acceptable values.

    allow_rewrite alone isn't sufficient here - unlike PATH_PREFIX,
    MAX_LENGTH, and NUMERIC_RANGE, there's no algorithmic "nearest member"
    of an arbitrary set. rewrite_value must also be explicitly supplied;
    if it isn't, this fails closed (same as allow_rewrite=False) rather
    than guessing a substitute.
    """
    allowed = constraint.value

    if value in allowed:
        return _FieldOutcome(valid=True)

    if constraint.allow_rewrite and constraint.rewrite_value is not None:
        return _FieldOutcome(valid=True, rewritten=True, new_value=constraint.rewrite_value)

    return _FieldOutcome(
        valid=False,
        violation_reason=f"value '{value}' is not one of the allowed values {allowed}",
    )


def _check_numeric_range(value: Any, constraint: ArgumentConstraint) -> _FieldOutcome:
    """constraint.value is an inclusive (min, max) pair. allow_rewrite
    clamps to the nearest bound."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # bool is technically an int subclass in Python; excluded
        # explicitly so a stray True/False is never silently treated as
        # 1/0 by a numeric-range check.
        return _FieldOutcome(valid=False, violation_reason=f"value '{value}' is not numeric")

    minimum, maximum = constraint.value

    if minimum <= value <= maximum:
        return _FieldOutcome(valid=True)

    if not constraint.allow_rewrite:
        return _FieldOutcome(
            valid=False,
            violation_reason=f"value {value} is outside allowed range [{minimum}, {maximum}]",
        )

    return _FieldOutcome(valid=True, rewritten=True, new_value=max(minimum, min(value, maximum)))


_CONSTRAINT_HANDLERS: dict[ConstraintType, Callable[[Any, ArgumentConstraint], _FieldOutcome]] = {
    ConstraintType.PATH_PREFIX: _check_path_prefix,
    ConstraintType.REGEX: _check_regex,
    ConstraintType.MAX_LENGTH: _check_max_length,
    ConstraintType.ALLOWED_VALUES: _check_allowed_values,
    ConstraintType.NUMERIC_RANGE: _check_numeric_range,
}


class ConstraintEvaluator:
    """Checks one arguments dict against a rule's ArgumentConstraint list.
    Has no notion of which rule it's serving, what action that rule maps
    to, or what happens after - that's RuleEvaluator's job, below.
    """

    def evaluate(
        self,
        arguments: dict[str, Any],
        constraints: Sequence[ArgumentConstraint],
    ) -> ConstraintResult:
        """Constraints are applied in the order given - PolicyRule's
        declaration order, never sorted or reordered. This matters when
        more than one constraint targets the same field: each later
        constraint sees whatever the previous one already rewrote, not
        the call's original value. That chaining is what lets a rule say
        "force this under /sandbox/, then cap its length" and have the
        length check apply to the already-sandboxed path.
        """

        working_arguments = dict(arguments)
        violations: list[str] = []
        any_rewritten = False

        for constraint in constraints:

            if constraint.field not in arguments:
                # A constraint on an argument the call didn't supply has
                # nothing to check. Treated as not-applicable, not a
                # violation: "this argument must be present" is schema
                # validation, a different concern from "this argument's
                # value must look like X", which is all a constraint
                # actually claims to police.
                continue

            current_value = working_arguments[constraint.field]
            outcome = self._check(current_value, constraint)

            if outcome.rewritten:
                working_arguments[constraint.field] = outcome.new_value
                any_rewritten = True
            elif not outcome.valid:
                violations.append(
                    outcome.violation_reason
                    or f"argument '{constraint.field}' violates {constraint.constraint_type.value}"
                )

        if violations:
            return ConstraintResult(
                valid=False,
                rewritten=any_rewritten,
                rewritten_arguments=working_arguments if any_rewritten else None,
                violation_reason="; ".join(violations),
            )

        return ConstraintResult(
            valid=True,
            rewritten=any_rewritten,
            rewritten_arguments=working_arguments if any_rewritten else None,
        )

    @staticmethod
    def _check(value: Any, constraint: ArgumentConstraint) -> _FieldOutcome:
        handler = _CONSTRAINT_HANDLERS.get(constraint.constraint_type)
        if handler is None:
            # Defensive: a ConstraintType added later without a handler
            # registered above fails closed (violation), not open.
            return _FieldOutcome(
                valid=False,
                violation_reason=(
                    f"no handler implemented for constraint type "
                    f"'{constraint.constraint_type.value}'"
                ),
            )
        return handler(value, constraint)


# ----------------------------------------------------------------------
# RuleEvaluator
# ----------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class RuleEvaluationResult:
    """Complete output of evaluating one tool call against a rule set.

    decision_outcome is PENDING_APPROVAL when the winning rule's action
    is REQUIRE_APPROVAL and constraints passed - this module never waits
    for or resolves an approval itself (that's approvals.py and
    engine.py's job), it only classifies that one is now needed.
    engine.py is expected to resolve PENDING_APPROVAL into a terminal
    outcome before anything reaches ToolLoop.
    """
    matched_rule: PolicyRule | None
    decision_outcome: DecisionOutcome
    rewritten_arguments: dict[str, Any] | None = None
    reason: str | None = None

    def effective_arguments(self, original_arguments: dict[str, Any]) -> dict[str, Any]:
        """Arguments to actually execute with: the rewritten set if any
        constraint rewrote something, otherwise the call's original
        arguments unchanged. rewritten_arguments itself deliberately
        stays None when nothing changed (that's what makes it a clean
        audit signal in PolicyDecisionLog) - this method is the
        convenience callers want without losing that distinction.
        """
        return self.rewritten_arguments if self.rewritten_arguments is not None else original_arguments


class RuleEvaluator:
    """High-level facade composing RuleMatcher, PriorityResolver, and
    ConstraintEvaluator. The only class in this module most callers
    (engine.py) need to know about.
    """

    def __init__(self) -> None:
        self._matcher = RuleMatcher()
        self._resolver = PriorityResolver()
        self._constraints = ConstraintEvaluator()

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        rules: Sequence[PolicyRule],
    ) -> RuleEvaluationResult:

        matches = self._matcher.match(tool_name, rules)
        winner = self._resolver.resolve(matches)

        if winner is None:
            # No rule has an opinion on this tool: default-allow. A
            # deliberate policy stance, not an oversight - guardrails
            # like "never allow delete_file" only make sense against a
            # backdrop where everything else is permitted unless named.
            # Flip to default-deny here in one line if that posture is
            # ever preferred instead.
            return RuleEvaluationResult(
                matched_rule=None,
                decision_outcome=DecisionOutcome.ALLOWED,
                reason="no matching rule (default allow)",
            )

        if winner.action is RuleAction.BLOCK:
            # Unconditional - constraints attached to a BLOCK rule, if
            # any, are not evaluated, since there's no "allowed but
            # adjusted" outcome for them to act on: a blocked call never
            # executes, so there's nothing for a rewrite to apply to.
            return RuleEvaluationResult(
                matched_rule=winner,
                decision_outcome=DecisionOutcome.BLOCKED,
                reason=winner.reason or f"blocked by rule '{winner.name}'",
            )

        constraint_result = self._constraints.evaluate(arguments, winner.constraints)

        if not constraint_result.valid:
            # A constraint violation overrides ALLOW and REQUIRE_APPROVAL
            # alike - no point asking a human to approve a call that
            # already fails basic input validation.
            return RuleEvaluationResult(
                matched_rule=winner,
                decision_outcome=DecisionOutcome.BLOCKED,
                reason=constraint_result.violation_reason,
            )

        if winner.action is RuleAction.REQUIRE_APPROVAL:
            return RuleEvaluationResult(
                matched_rule=winner,
                decision_outcome=DecisionOutcome.PENDING_APPROVAL,
                rewritten_arguments=constraint_result.rewritten_arguments,
                reason=winner.reason,
            )

        # ALLOW, constraints satisfied (possibly via rewrite).
        return RuleEvaluationResult(
            matched_rule=winner,
            decision_outcome=(
                DecisionOutcome.REWRITTEN if constraint_result.rewritten
                else DecisionOutcome.ALLOWED
            ),
            rewritten_arguments=constraint_result.rewritten_arguments,
            reason=winner.reason,
        )