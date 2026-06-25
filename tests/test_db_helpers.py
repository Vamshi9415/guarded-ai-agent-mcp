import pytest

from datetime import datetime, timezone

from bson import ObjectId

from backend import db


def test_create_rule_uppercases_action_and_defaults_enabled(monkeypatch, fake_collection):
    rules = fake_collection([])
    monkeypatch.setattr(db, "get_rules_collection", lambda: rules)

    rule_id = db.create_rule({"tool_name": "delete_file", "action": "block"})

    assert rule_id == "id-1"
    assert rules.docs[0]["action"] == "BLOCK"
    assert rules.docs[0]["enabled"] is True
    assert isinstance(rules.docs[0]["created_at"], datetime)


def test_get_all_rules_serializes_ids_and_datetimes(monkeypatch, fake_collection):
    object_id = ObjectId()
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    rules = fake_collection([{"_id": object_id, "tool_name": "read_file", "created_at": now, "updated_at": now}])
    monkeypatch.setattr(db, "get_rules_collection", lambda: rules)

    result = db.get_all_rules()

    assert result == [{
        "_id": str(object_id),
        "tool_name": "read_file",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }]


def test_toggle_rule_flips_enabled_when_no_state_provided(monkeypatch, fake_collection):
    object_id = ObjectId()
    rules = fake_collection([{"_id": object_id, "enabled": True}])
    monkeypatch.setattr(db, "get_rules_collection", lambda: rules)

    changed = db.toggle_rule(str(object_id))

    assert changed is True
    assert rules.docs[0]["enabled"] is False
    assert "updated_at" in rules.docs[0]


def test_toggle_rule_can_set_explicit_state(monkeypatch, fake_collection):
    object_id = ObjectId()
    rules = fake_collection([{"_id": object_id, "enabled": False}])
    monkeypatch.setattr(db, "get_rules_collection", lambda: rules)

    changed = db.toggle_rule(str(object_id), enabled=True)

    assert changed is True
    assert rules.docs[0]["enabled"] is True


def test_toggle_rule_returns_false_for_missing_rule(monkeypatch, fake_collection):
    rules = fake_collection([])
    monkeypatch.setattr(db, "get_rules_collection", lambda: rules)

    assert db.toggle_rule(str(ObjectId())) is False


def test_delete_rule(monkeypatch, fake_collection):
    object_id = ObjectId()
    rules = fake_collection([{"_id": object_id}])
    monkeypatch.setattr(db, "get_rules_collection", lambda: rules)

    assert db.delete_rule(str(object_id)) is True
    assert rules.docs == []


def test_get_recent_logs_serializes_timestamps(monkeypatch, fake_collection):
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    logs = fake_collection([
        {"tool_name": "old", "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc)},
        {"tool_name": "new", "timestamp": now},
    ])
    monkeypatch.setattr(db, "get_logs_collection", lambda: logs)

    result = db.get_recent_logs(limit=1)

    assert result == [{"tool_name": "new", "timestamp": now.isoformat()}]


def test_create_approval_request_persists_pending_doc(monkeypatch, fake_collection):
    approvals = fake_collection([])
    monkeypatch.setattr(db, "get_approvals_collection", lambda: approvals)

    approval_id = db.create_approval_request("c1", "local", "write_file", {"path": "a.txt"})

    assert approval_id == "id-1"
    assert approvals.docs[0]["conversation_id"] == "c1"
    assert approvals.docs[0]["server_id"] == "local"
    assert approvals.docs[0]["tool_name"] == "write_file"
    assert approvals.docs[0]["tool_args"] == {"path": "a.txt"}
    assert approvals.docs[0]["status"] == "pending"


def test_create_approval_request_from_data_persists_pending_doc(monkeypatch, fake_collection):
    approvals = fake_collection([])
    monkeypatch.setattr(db, "get_approvals_collection", lambda: approvals)

    approval_id = db.create_approval_request_from_data({
        "conversation_id": "c1",
        "server_id": "remote",
        "tool_name": "search",
        "tool_args": {"q": "docs"},
        "reason": "review",
    })

    assert approval_id == "id-1"
    assert approvals.docs[0]["server_id"] == "remote"
    assert approvals.docs[0]["reason"] == "review"

@pytest.mark.asyncio
async def test_log_tool_action_persists_audit_doc(monkeypatch, fake_collection):
    logs = fake_collection([])
    monkeypatch.setattr(db, "get_logs_collection", lambda: logs)

    inserted_id = await db.log_tool_action("c1", "local", "read_file", {"path": "a.txt"}, "ALLOW", "ok")

    assert inserted_id == "id-1"
    assert logs.docs[0]["conversation_id"] == "c1"
    assert logs.docs[0]["server_id"] == "local"
    assert logs.docs[0]["tool_args"] == {"path": "a.txt"}
    assert logs.docs[0]["decision"] == "ALLOW"



