import pytest

from backend import policy


@pytest.fixture(autouse=True)
def reset_policy_indexes():
    policy._indexes_ready = False
    yield
    policy._indexes_ready = False


@pytest.mark.asyncio
async def test_policy_allows_when_no_rules(monkeypatch, fake_collection):
    rules = fake_collection([])
    logs = fake_collection([])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: logs)

    decision = await policy.PolicyEngine.evaluate_tool("local", "read_file", {"path": "safe.txt"})

    assert decision == {"action": "ALLOW", "reason": "No restrictive rule matched"}
    assert rules.indexes == [[("tool_name", 1), ("enabled", 1)]]


@pytest.mark.asyncio
async def test_block_rule_wins_over_all_other_rules(monkeypatch, fake_collection):
    rules = fake_collection([
        {"tool_name": "read_file", "action": "REQUIRE_APPROVAL", "enabled": True},
        {"tool_name": "read_file", "action": "BLOCK", "enabled": True, "reason": "danger"},
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("local", "read_file", {"path": "safe.txt"})

    assert decision["action"] == "BLOCK"
    assert decision["reason"] == "danger"


@pytest.mark.asyncio
async def test_block_rule_can_target_qualified_tool_name(monkeypatch, fake_collection):
    rules = fake_collection([
        {"tool_name": "remote__search", "action": "BLOCK", "enabled": True, "reason": "no web"},
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("remote", "search", {"q": "secrets"})

    assert decision == {"action": "BLOCK", "reason": "no web"}


@pytest.mark.asyncio
async def test_wildcard_block_applies_to_every_tool(monkeypatch, fake_collection):
    rules = fake_collection([
        {"tool_name": "*", "action": "BLOCK", "enabled": True, "reason": "maintenance"},
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("any", "anything", {})

    assert decision["action"] == "BLOCK"
    assert decision["reason"] == "maintenance"


@pytest.mark.asyncio
async def test_disabled_rules_are_ignored(monkeypatch, fake_collection):
    rules = fake_collection([
        {"tool_name": "delete_file", "action": "BLOCK", "enabled": False},
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("local", "delete_file", {})

    assert decision["action"] == "ALLOW"


@pytest.mark.asyncio
async def test_input_validation_blocks_bad_path(monkeypatch, fake_collection):
    rules = fake_collection([
        {
            "action": "INPUT_VALIDATION",
            "enabled": True,
            "config": {"field": "path", "operator": "start_with", "value": "/sandbox/"},
        }
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("local", "write_file", {"path": "/etc/passwd"})

    assert decision["action"] == "BLOCK"
    assert "Input validation failed" in decision["reason"]


@pytest.mark.asyncio
async def test_input_validation_allows_matching_path(monkeypatch, fake_collection):
    rules = fake_collection([
        {
            "action": "INPUT_VALIDATION",
            "enabled": True,
            "condition": {"field": "path", "operator": "start_with", "value": "/sandbox/"},
        }
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("local", "write_file", {"path": "/sandbox/a.txt"})

    assert decision["action"] == "ALLOW"


@pytest.mark.parametrize(
    "condition,args,valid",
    [
        ({"field": "path", "operator": "contains", "value": "safe"}, {"path": "safe/a.txt"}, True),
        ({"field": "path", "operator": "contains", "value": "safe"}, {"path": "tmp/a.txt"}, False),
        ({"field": "mode", "operator": "not_equals", "value": "delete"}, {"mode": "read"}, True),
        ({"field": "mode", "operator": "not_equals", "value": "delete"}, {"mode": "delete"}, False),
        ({"field": "path", "operator": "regex", "value": r"^[a-z]+\.txt$"}, {"path": "notes.txt"}, True),
        ({"field": "path", "operator": "regex", "value": r"^[a-z]+\.txt$"}, {"path": "../notes.txt"}, False),
    ],
)
def test_validate_inputs_operators(condition, args, valid):
    assert policy.PolicyEngine._validate_inputs(args, condition)["valid"] is valid


@pytest.mark.asyncio
async def test_require_approval_rule(monkeypatch, fake_collection):
    rules = fake_collection([
        {"tool_name": "delete_file", "action": "REQUIRE_APPROVAL", "enabled": True, "reason": "human needed"},
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: fake_collection([]))

    decision = await policy.PolicyEngine.evaluate_tool("local", "delete_file", {"path": "a.txt"})

    assert decision == {"action": "REQUIRE_APPROVAL", "reason": "human needed"}


@pytest.mark.asyncio
async def test_token_budget_blocks_when_limit_reached(monkeypatch, fake_collection):
    rules = fake_collection([
        {"action": "TOKEN_BUDGET", "enabled": True, "config": {"max_tokens": 2}},
    ])
    logs = fake_collection([
        {"conversation_id": "default"},
        {"conversation_id": "default"},
        {"conversation_id": "other"},
    ])
    monkeypatch.setattr(policy, "get_rules_collection", lambda: rules)
    monkeypatch.setattr(policy, "get_logs_collection", lambda: logs)

    decision = await policy.PolicyEngine.evaluate_tool("local", "read_file", {})

    assert decision["action"] == "BLOCK"
    assert "Token budget exceeded" in decision["reason"]


@pytest.mark.asyncio
async def test_policy_allows_when_policy_store_unavailable(monkeypatch):
    def unavailable():
        raise policy.MongoUnavailable("dns timeout")

    monkeypatch.setattr(policy, "get_rules_collection", unavailable)

    decision = await policy.PolicyEngine.evaluate_tool("local", "read_file", {})

    assert decision["action"] == "ALLOW"
    assert "Policy store unavailable" in decision["reason"]
