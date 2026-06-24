"""
PolicyEngine --- The Guardrails Brain
Three actions: BLOCK / ALLOW / REQUIRE_APPROVAL
Rule types: block_tool, require_approval, input_validation, token_budget
Rules stored in MongoDB --- changes propagate without restart
"""

import os
import re
from typing import Any, Dict

from .db import get_logs_collection, get_rules_collection


_indexes_ready = False


def _rules_col():
    global _indexes_ready
    collection = get_rules_collection()
    if not _indexes_ready:
        collection.create_index([("tool_name", 1), ("enabled", 1)])
        _indexes_ready = True
    return collection


class PolicyEngine:
    """
    evaluates tool calls against guardrail rules stored in MongoDB.
    Three possible decisions: BLOCK / ALLOW / REQUIRE_APPROVAL
    """

    @classmethod
    async def evaluate_tool(
        cls, server_id: str, tool_name: str, tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        rules_col = _rules_col()

        # 1. Check BLOCK rules (highest priority --- deny immediately)
        block_rule = rules_col.find_one({
            "tool_name": tool_name,
            "action": "BLOCK",
            "enabled": True,
        })
        if block_rule:
            return {"action": "BLOCK", "reason": block_rule.get("reason", "Blocked by policy")}

        # 2. Check INPUT_VALIDATION rules
        validation_rule = rules_col.find_one({
            "enabled": True,
            "action": "INPUT_VALIDATION",
        })
        if validation_rule:
            condition = validation_rule.get("condition") or validation_rule.get("config", {})
            validated = cls._validate_inputs(tool_args, condition)
            if not validated["valid"]:
                return {"action": "BLOCK", "reason": f"Input validation failed: {validated['message']}"}

        # 3. Check REQUIRE_APPROVAL rules
        approval_rule = rules_col.find_one({
            "tool_name": tool_name,
            "action": "REQUIRE_APPROVAL",
            "enabled": True,
        })
        if approval_rule:
            return {"action": "REQUIRE_APPROVAL", "reason": approval_rule.get("reason", "Requires human approval")}

        # 4. Check TOKEN_BUDGET rule (per conversation)
        budget_rule = rules_col.find_one({
            "action": "TOKEN_BUDGET",
            "enabled": True,
        })
        if budget_rule:
            conversation_id = os.environ.get("CONVERSATION_ID", "default")
            config = budget_rule.get("config", {})
            max_tokens = config.get("max_tokens", budget_rule.get("max_tokens", 10000))
            total_tokens = get_logs_collection().count_documents({"conversation_id": conversation_id})
            if total_tokens >= max_tokens:
                return {"action": "BLOCK", "reason": f"Token budget exceeded ({total_tokens} >= {max_tokens})"}

        # 5. No matching rules --- ALLOW by default
        return {"action": "ALLOW", "reason": "No restrictive rule matched"}

    @classmethod
    def _validate_inputs(cls, args: Dict, condition: Dict) -> Dict:
        """
        Validates tool arguments against a condition stored in MongoDB.
        condition format: { "field": "path", "operator": "start_with", "value": "/sandbox/" }
        """
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        if not field or not operator:
            return {"valid": True, "message": "No validation condition set"}

        arg_value = args.get(field, "")

        if operator == "start_with" and not str(arg_value).startswith(value):
            return {"valid": False, "message": f"Field '{field}' must start with '{value}'"}
        if operator == "contains" and value and value not in str(arg_value):
            return {"valid": False, "message": f"Field '{field}' must contain '{value}'"}
        if operator == "not_equals" and str(arg_value) == str(value):
            return {"valid": False, "message": f"Field '{field}' must not equal '{value}'"}
        if operator == "regex":
            if not re.match(value, str(arg_value)):
                return {"valid": False, "message": f"Field '{field}' must match pattern '{value}'"}

        return {"valid": True, "message": "Validation passed"}
