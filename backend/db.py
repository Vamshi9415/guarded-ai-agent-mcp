"""
db.py — MongoDB Atlas connection + audit logging
All tool calls (allowed, blocked, pending) are logged here.
Collections:
  guarded_ai.tool_logs      — audit trail of every tool call
  guarded_ai.guardrail_rules — policy rules (read by PolicyEngine)
  guarded_ai.approvals       — pending approval requests
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from typing import Any, Dict, Optional


# --- Connection -------------------------------------------------------
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")

_mongo_client: Optional[MongoClient] = None


def get_db():
    """Lazy singleton — reuse the same MongoClient across the app lifetime."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        # Quick ping to verify connection works on first use
        try:
            _mongo_client.admin.command("ping")
            print("MongoDB connected successfully")
        except ConnectionFailure as e:
            print(f"MongoDB connection failed: {e}")
    return _mongo_client["guarded_ai"]


# --- Collections convenience ------------------------------------------
def get_rules_collection():
    return get_db()["guardrail_rules"]


def get_logs_collection():
    return get_db()["tool_logs"]


def get_approvals_collection():
    return get_db()["approvals"]


# --- Audit Log --------------------------------------------------------
async def log_tool_action(
    conversation_id: str,
    server_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
    decision: str,
    reason: str = "",
) -> str:
    """
    Persists every tool call attempt to MongoDB.
    Returns the inserted document ID as a string.
    """
    doc = {
        "conversation_id": conversation_id,
        "server_id": server_id,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "decision": decision,          # ALLOW / BLOCK / REQUIRE_APPROVAL
        "reason": reason,
        "timestamp": datetime.now(timezone.utc),
    }
    result = get_logs_collection().insert_one(doc)
    return str(result.inserted_id)


# --- Rules CRUD -------------------------------------------------------
def create_rule(rule: Dict[str, Any]) -> str:
    """Insert a new guardrail rule. Returns the new rule's string ID."""
    rule["created_at"] = datetime.now(timezone.utc)
    rule.setdefault("enabled", True)
    result = get_rules_collection().insert_one(rule)
    return str(result.inserted_id)


def get_all_rules() -> list:
    """Return all guardrail rules as plain dicts."""
    rules = []
    for r in get_rules_collection().find({}, {"_id": 0}):
        rules.append(r)
    return rules


def toggle_rule(rule_id: str, enabled: bool) -> bool:
    """Enable or disable a rule by its string ID."""
    from bson import ObjectId
    result = get_rules_collection().update_one(
        {"_id": ObjectId(rule_id)},
        {"$set": {"enabled": enabled, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


def delete_rule(rule_id: str) -> bool:
    """Delete a guardrail rule by its string ID."""
    from bson import ObjectId
    result = get_rules_collection().delete_one({"_id": ObjectId(rule_id)})
    return result.deleted_count > 0


# --- Approvals --------------------------------------------------------
def create_approval_request(
    conversation_id: str,
    server_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> str:
    """Creates a pending approval record. Returns string ID."""
    doc = {
        "conversation_id": conversation_id,
        "server_id": server_id,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "status": "pending",           # pending / approved / denied / timeout
        "created_at": datetime.now(timezone.utc),
    }
    result = get_approvals_collection().insert_one(doc)
    return str(result.inserted_id)


def resolve_approval(approval_id: str, status: str) -> bool:
    """Approve or deny a pending request. status = 'approved' | 'denied'."""
    from bson import ObjectId
    result = get_approvals_collection().update_one(
        {"_id": ObjectId(approval_id), "status": "pending"},
        {"$set": {"status": status, "resolved_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


def get_pending_approvals() -> list:
    """Return all pending approval requests."""
    items = []
    for a in get_approvals_collection().find({"status": "pending"}):
        a["_id"] = str(a["_id"])
        items.append(a)
    return items


def get_recent_logs(limit: int = 50) -> list:
    """Return the most recent tool_log entries for the dashboard."""
    items = []
    for log in get_logs_collection().find({}, {"_id": 0}).sort("timestamp", -1).limit(limit):
        if "timestamp" in log:
            log["timestamp"] = log["timestamp"].isoformat()
        items.append(log)
    return items
