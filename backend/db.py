"""
db.py --- MongoDB Atlas connection + audit logging
All tool calls (allowed, blocked, pending) are logged here.
Collections:
  wms_database.tool_logs      --- audit trail of every tool call
  wms_database.guardrail_rules --- policy rules (read by PolicyEngine)
  wms_database.approvals       --- pending approval requests
"""

import os
from datetime import datetime, timezone
from time import monotonic
from pymongo import MongoClient
from typing import Any, Dict, Optional

from .mongo_config import get_mongo_db_name, get_mongo_heartbeat_ms, get_mongo_uri


# --- Connection -------------------------------------------------------
MONGODB_URI = get_mongo_uri()
MONGODB_DB_NAME = get_mongo_db_name()

_mongo_client: Optional[MongoClient] = None
_mongo_error: Optional[str] = None
_mongo_error_at: Optional[float] = None


class MongoUnavailable(RuntimeError):
    """Raised when MongoDB cannot be reached or initialized."""


def get_db():
    """Lazy singleton --- reuse the same MongoClient across the app lifetime."""
    global _mongo_client, _mongo_error, _mongo_error_at
    if _mongo_client is None:
        retry_after = int(os.environ.get("MONGO_RETRY_COOLDOWN_SECONDS", "30"))
        if _mongo_error and _mongo_error_at and monotonic() - _mongo_error_at < retry_after:
            raise MongoUnavailable(_mongo_error)
        try:
            client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                heartbeatFrequencyMS=get_mongo_heartbeat_ms(),
            )
            client.admin.command("ping")
            _mongo_client = client
            _mongo_error = None
            _mongo_error_at = None
            print("MongoDB connected successfully")
        except Exception as e:
            _mongo_client = None
            _mongo_error = str(e)
            _mongo_error_at = monotonic()
            print(f"MongoDB unavailable: {_mongo_error}")
            raise MongoUnavailable(_mongo_error) from e

    return _mongo_client[MONGODB_DB_NAME]

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
    try:
        result = get_logs_collection().insert_one(doc)
    except MongoUnavailable:
        return ""
    return str(result.inserted_id)


# --- Rules CRUD -------------------------------------------------------
def create_rule(rule: Dict[str, Any]) -> str:
    """Insert a new guardrail rule. Returns the new rule's string ID."""
    if "action" in rule:
        rule["action"] = str(rule["action"]).upper()
    rule["created_at"] = datetime.now(timezone.utc)
    rule.setdefault("enabled", True)
    result = get_rules_collection().insert_one(rule)
    return str(result.inserted_id)


def get_all_rules() -> list:
    """Return all guardrail rules as plain dicts."""
    rules = []
    for r in get_rules_collection().find({}):
        r["_id"] = str(r["_id"])
        if "created_at" in r:
            r["created_at"] = r["created_at"].isoformat()
        if "updated_at" in r:
            r["updated_at"] = r["updated_at"].isoformat()
        rules.append(r)
    return rules


def toggle_rule(rule_id: str, enabled: bool | None = None) -> bool:
    """Enable, disable, or flip a rule by its string ID."""
    from bson import ObjectId
    object_id = ObjectId(rule_id)
    if enabled is None:
        existing = get_rules_collection().find_one({"_id": object_id}, {"enabled": 1})
        if not existing:
            return False
        enabled = not existing.get("enabled", True)

    result = get_rules_collection().update_one(
        {"_id": object_id},
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
    try:
        result = get_approvals_collection().insert_one(doc)
    except MongoUnavailable:
        return ""
    return str(result.inserted_id)


def resolve_approval(approval_id: str, status: str) -> bool:
    """Approve or deny a pending request. status = 'approved' | 'denied'."""
    from bson import ObjectId
    result = get_approvals_collection().update_one(
        {"_id": ObjectId(approval_id), "status": "pending"},
        {"$set": {"status": status, "resolved_at": datetime.now(timezone.utc)}},
    )
    return result.modified_count > 0


def create_approval_request_from_data(data: dict) -> str:
    """Create a pending approval request from an API-style payload."""
    approval_doc = {
        "conversation_id": data.get("conversation_id", "default"),
        "server_id": data.get("server_id", ""),
        "tool_name": data["tool_name"],
        "tool_args": data["tool_args"],
        "reason": data.get("reason", "Requires approval"),
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }
    result = get_approvals_collection().insert_one(approval_doc)
    return str(result.inserted_id)


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
