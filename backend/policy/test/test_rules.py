# backend/policy/test/test_rules.py
"""
Unit tests for backend/policy/rules.py.

Pure module, no mocks needed: every test builds plain PolicyRule /
ArgumentConstraint instances and asserts on RuleEvaluator's output.

Run with: pytest backend/policy/test/test_rules.py
"""
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.policy.models import (
    ArgumentConstraint,
    ConstraintType,
    DecisionOutcome,
    PolicyRule,
    RuleAction,
    RuleType,
)
from backend.policy.rules import RuleEvaluator


def make_rule(**overrides) -> PolicyRule:
    defaults = dict(
        name="test-rule",
        action=RuleAction.ALLOW,
        tool_pattern="*",
        rule_type=RuleType.GLOB,
        priority=0,
    )
    defaults.update(overrides)
    return PolicyRule(**defaults)


evaluator = RuleEvaluator()


# ---------------------------------------------------------------- matching

def test_exact_match():
    rule = make_rule(rule_type=RuleType.EXACT, tool_pattern="delete_record", action=RuleAction.BLOCK)
    assert evaluator.evaluate("delete_record", {}, [rule]).decision_outcome is DecisionOutcome.BLOCKED
    assert evaluator.evaluate("delete_record_v2", {}, [rule]).decision_outcome is DecisionOutcome.ALLOWED


def test_glob_match():
    rule = make_rule(rule_type=RuleType.GLOB, tool_pattern="delete_*", action=RuleAction.BLOCK)
    assert evaluator.evaluate("delete_record", {}, [rule]).decision_outcome is DecisionOutcome.BLOCKED
    assert evaluator.evaluate("create_record", {}, [rule]).decision_outcome is DecisionOutcome.ALLOWED


def test_regex_match_is_fullmatch_not_search():
    rule = make_rule(rule_type=RuleType.REGEX, tool_pattern="delete_record", action=RuleAction.BLOCK)
    assert evaluator.evaluate("delete_record", {}, [rule]).decision_outcome is DecisionOutcome.BLOCKED

    substring_rule = make_rule(rule_type=RuleType.REGEX, tool_pattern="record", action=RuleAction.BLOCK)
    assert evaluator.evaluate("delete_record", {}, [substring_rule]).decision_outcome is DecisionOutcome.ALLOWED


def test_disabled_rule_never_matches():
    rule = make_rule(tool_pattern="delete_record", rule_type=RuleType.EXACT,
                      action=RuleAction.BLOCK, enabled=False)
    assert evaluator.evaluate("delete_record", {}, [rule]).decision_outcome is DecisionOutcome.ALLOWED


# --------------------------------------------------------------- priority

def test_higher_priority_wins():
    block = make_rule(tool_pattern="delete_record", rule_type=RuleType.EXACT,
                       action=RuleAction.BLOCK, priority=100)
    allow_all = make_rule(tool_pattern="*", rule_type=RuleType.GLOB,
                           action=RuleAction.ALLOW, priority=50)
    result = evaluator.evaluate("delete_record", {}, [allow_all, block])
    assert result.decision_outcome is DecisionOutcome.BLOCKED
    assert result.matched_rule.id == block.id


def test_equal_priority_block_beats_approval_beats_allow():
    block = make_rule(tool_pattern="x", rule_type=RuleType.EXACT, action=RuleAction.BLOCK, priority=10)
    approval = make_rule(tool_pattern="x", rule_type=RuleType.EXACT,
                          action=RuleAction.REQUIRE_APPROVAL, priority=10)
    allow = make_rule(tool_pattern="x", rule_type=RuleType.EXACT, action=RuleAction.ALLOW, priority=10)

    assert evaluator.evaluate("x", {}, [approval, allow, block]).decision_outcome is DecisionOutcome.BLOCKED
    assert evaluator.evaluate("x", {}, [allow, approval]).decision_outcome is DecisionOutcome.PENDING_APPROVAL


def test_tiebreak_is_deterministic_regardless_of_list_order():
    rule_a = make_rule(tool_pattern="x", rule_type=RuleType.EXACT, action=RuleAction.ALLOW, priority=10)
    rule_b = make_rule(tool_pattern="x", rule_type=RuleType.EXACT, action=RuleAction.ALLOW, priority=10)
    winner_first = evaluator.evaluate("x", {}, [rule_a, rule_b]).matched_rule
    winner_reordered = evaluator.evaluate("x", {}, [rule_b, rule_a]).matched_rule
    assert winner_first.id == winner_reordered.id


# ----------------------------------------------------------- constraints

def test_path_prefix_rewrite_strips_traversal():
    constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.PATH_PREFIX,
        value="/sandbox", allow_rewrite=True,
    )
    rule = make_rule(tool_pattern="write_file", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("write_file", {"path": "../../etc/passwd"}, [rule])
    assert result.decision_outcome is DecisionOutcome.REWRITTEN
    assert result.rewritten_arguments["path"] == "/sandbox/etc/passwd"


def test_path_prefix_blocks_without_rewrite_permission():
    constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.PATH_PREFIX,
        value="/sandbox", allow_rewrite=False,
    )
    rule = make_rule(tool_pattern="write_file", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("write_file", {"path": "/etc/passwd"}, [rule])
    assert result.decision_outcome is DecisionOutcome.BLOCKED


def test_path_prefix_rejects_lookalike_prefix():
    constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.PATH_PREFIX,
        value="/sandbox", allow_rewrite=False,
    )
    rule = make_rule(tool_pattern="write_file", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("write_file", {"path": "/sandboxevil/x"}, [rule])
    assert result.decision_outcome is DecisionOutcome.BLOCKED


def test_regex_constraint_never_rewritten():
    constraint = ArgumentConstraint(
        field="key", constraint_type=ConstraintType.REGEX,
        value=r"user_\d+", allow_rewrite=True,  # ignored for REGEX, by design
    )
    rule = make_rule(tool_pattern="read_record", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    assert evaluator.evaluate("read_record", {"key": "user_1"}, [rule]).decision_outcome is DecisionOutcome.ALLOWED
    assert evaluator.evaluate("read_record", {"key": "admin"}, [rule]).decision_outcome is DecisionOutcome.BLOCKED


def test_allowed_values_uses_explicit_rewrite_value():
    constraint = ArgumentConstraint(
        field="role", constraint_type=ConstraintType.ALLOWED_VALUES,
        value=["viewer", "editor"], allow_rewrite=True, rewrite_value="viewer",
    )
    rule = make_rule(tool_pattern="create_record", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("create_record", {"role": "admin"}, [rule])
    assert result.decision_outcome is DecisionOutcome.REWRITTEN
    assert result.rewritten_arguments["role"] == "viewer"


def test_allowed_values_blocks_without_explicit_rewrite_value():
    constraint = ArgumentConstraint(
        field="role", constraint_type=ConstraintType.ALLOWED_VALUES,
        value=["viewer", "editor"], allow_rewrite=True, rewrite_value=None,
    )
    rule = make_rule(tool_pattern="create_record", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("create_record", {"role": "admin"}, [rule])
    assert result.decision_outcome is DecisionOutcome.BLOCKED


def test_numeric_range_clamps():
    constraint = ArgumentConstraint(
        field="brightness", constraint_type=ConstraintType.NUMERIC_RANGE,
        value=(0, 100), allow_rewrite=True,
    )
    rule = make_rule(tool_pattern="set_light", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("set_light", {"brightness": 150}, [rule])
    assert result.decision_outcome is DecisionOutcome.REWRITTEN
    assert result.rewritten_arguments["brightness"] == 100


def test_max_length_truncates():
    constraint = ArgumentConstraint(
        field="note", constraint_type=ConstraintType.MAX_LENGTH,
        value=5, allow_rewrite=True,
    )
    rule = make_rule(tool_pattern="create_record", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    result = evaluator.evaluate("create_record", {"note": "hello world"}, [rule])
    assert result.decision_outcome is DecisionOutcome.REWRITTEN
    assert result.rewritten_arguments["note"] == "hello"


def test_cascading_constraints_see_prior_rewrite():
    # Regression test for the working_arguments bug caught in review: a
    # later constraint on the same field must see the earlier
    # constraint's rewrite, not the call's original value. MAX_LENGTH=25
    # would BLOCK on the 34-char original, but the 20-char value
    # PATH_PREFIX rewrites it to comfortably fits - this only passes if
    # the constraints actually chain.
    path_constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.PATH_PREFIX,
        value="/sandbox", allow_rewrite=True,
    )
    length_constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.MAX_LENGTH,
        value=25, allow_rewrite=False,
    )
    rule = make_rule(
        tool_pattern="write_file", rule_type=RuleType.EXACT, action=RuleAction.ALLOW,
        constraints=[path_constraint, length_constraint],
    )
    original = {"path": "../../../../../../../../etc/passwd"}
    result = evaluator.evaluate("write_file", original, [rule])
    assert result.decision_outcome is DecisionOutcome.REWRITTEN
    assert result.rewritten_arguments["path"] == "/sandbox/etc/passwd"


def test_missing_argument_is_not_a_violation():
    constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.PATH_PREFIX, value="/sandbox",
    )
    rule = make_rule(tool_pattern="list_records", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    assert evaluator.evaluate("list_records", {}, [rule]).decision_outcome is DecisionOutcome.ALLOWED


# ------------------------------------------------------------- approvals

def test_require_approval_is_pending_not_resolved():
    rule = make_rule(tool_pattern="delete_record", rule_type=RuleType.EXACT,
                      action=RuleAction.REQUIRE_APPROVAL)
    result = evaluator.evaluate("delete_record", {}, [rule])
    assert result.decision_outcome is DecisionOutcome.PENDING_APPROVAL
    assert result.matched_rule.action is RuleAction.REQUIRE_APPROVAL


def test_constraint_violation_overrides_require_approval():
    constraint = ArgumentConstraint(
        field="path", constraint_type=ConstraintType.PATH_PREFIX,
        value="/sandbox", allow_rewrite=False,
    )
    rule = make_rule(
        tool_pattern="write_file", rule_type=RuleType.EXACT,
        action=RuleAction.REQUIRE_APPROVAL, constraints=[constraint],
    )
    result = evaluator.evaluate("write_file", {"path": "/etc/passwd"}, [rule])
    assert result.decision_outcome is DecisionOutcome.BLOCKED  # no point asking a human


# ------------------------------------------------------------- defaults

def test_no_rules_default_allows():
    result = evaluator.evaluate("anything", {}, [])
    assert result.decision_outcome is DecisionOutcome.ALLOWED
    assert result.matched_rule is None


def test_effective_arguments_falls_back_to_original_when_unrewritten():
    rule = make_rule(tool_pattern="read_record", rule_type=RuleType.EXACT, action=RuleAction.ALLOW)
    original = {"key": "user_1"}
    result = evaluator.evaluate("read_record", original, [rule])
    assert result.rewritten_arguments is None
    assert result.effective_arguments(original) == original


def test_effective_arguments_returns_rewritten_when_present():
    constraint = ArgumentConstraint(
        field="brightness", constraint_type=ConstraintType.NUMERIC_RANGE,
        value=(0, 100), allow_rewrite=True,
    )
    rule = make_rule(tool_pattern="set_light", rule_type=RuleType.EXACT,
                      action=RuleAction.ALLOW, constraints=[constraint])
    original = {"brightness": 150}
    result = evaluator.evaluate("set_light", original, [rule])
    assert result.effective_arguments(original)["brightness"] == 100