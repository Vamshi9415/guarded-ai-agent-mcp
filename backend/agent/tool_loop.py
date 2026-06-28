# backend/agent/tool_loop.py
"""
The LLM <-> MCP tool-use loop, and nothing else.

ask model -> [policy check -> MCP execute -> feed result back]* -> final
text. No policy *rules* live here, no MCP transport details live here -
just orchestration between BaseLLMClient and ToolRegistry, gated by
whatever PolicyEngine it's handed.

This file depends on a tiny structural Protocol (PolicyEngine,
PolicyDecision below), never on backend/policy/* directly - policy/engine.py
will implement that Protocol later. One-way dependency.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from ..llm.base import BaseLLMClient, Message, ToolCall, ToolSpec, Usage
from ..mcp.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_TOOL_TURNS_DEFAULT = 8


# ----------------------------------------------------------------------
# The policy port. policy/engine.py implements this; nothing here imports
# from the policy package.
# ----------------------------------------------------------------------

@dataclass
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    # Lets an input-validation rule rewrite/sanitize arguments before
    # execution (e.g. normalizing a path so it's forced under /sandbox/)
    # instead of only being able to allow or flat-out deny.
    arguments: dict[str, Any] | None = None


class PolicyEngine(Protocol):

    async def evaluate(
        self,
        *,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> PolicyDecision:
        """
        Final decision for one tool call. If the matching rule requires
        human approval, this call owns that entire wait (poll a
        pending-approvals store, apply a timeout, whatever) and only
        returns once it's resolved - the loop never sees "pending", only
        allowed/denied. An approver who's offline should resolve to a
        denial with a clear reason once the timeout fires, not a hang.
        """
        ...

    async def check_budget(
        self,
        *,
        conversation_id: str,
        usage: Usage,
    ) -> PolicyDecision:
        """Cumulative-usage check, run once per loop turn (not per tool
        call) - this is the "cost/token budget per conversation" rule."""
        ...


class StopReason(Enum):
    COMPLETED = "completed"
    BUDGET_EXCEEDED = "budget_exceeded"
    MAX_TOOL_TURNS = "max_turns_reached"


@dataclass
class ToolLoopResult:
    messages: list[Message]   # full updated conversation, tool turns included
    final_text: str | None
    tool_turns_used: int
    stop_reason: StopReason
    stop_detail: str | None = None  # e.g. the policy's budget-exceeded reason


class ToolLoop:

    def __init__(
        self,
        llm: BaseLLMClient,
        registry: ToolRegistry,
        policy: PolicyEngine,
        max_tool_turns: int = MAX_TOOL_TURNS_DEFAULT,
    ):
        self.llm = llm
        self.registry = registry
        self.policy = policy
        self.max_tool_turns = max_tool_turns

        # Cache of the provider-agnostic tool list, invalidated only when
        # the registry's tool set actually changes (a server connecting or
        # dropping mid-conversation) - not rebuilt on every turn.
        self._tool_spec_cache: list[ToolSpec] = []
        self._tool_spec_cache_key: frozenset[str] = frozenset()

    async def run(self, messages: list[Message], conversation_id: str) -> ToolLoopResult:

        messages = list(messages)  # never mutate the caller's list
        # total_usage = Usage()

        for turn in range(self.max_tool_turns):

            tools = self._current_tool_specs()
            print("\n========== AVAILABLE TOOLS ==========")
            for tool in tools:
                print(f"Name: {tool.name}")
                print(f"Description: {tool.description}")
                print(f"Parameters: {tool.parameters}")
            print("=====================================\n")
            response = await self.llm.generate(messages, tools)
            # total_usage = total_usage + response.usage

            if not response.wants_tool_call:
                messages.append(Message.assistant(text=response.content, raw=response.raw))
                return ToolLoopResult(
                    messages=messages,
                    final_text=response.content,
                    tool_turns_used=turn,
                    stop_reason=StopReason.COMPLETED,
                )

            budget = await self.policy.check_budget(
                conversation_id=conversation_id, usage=response.usage
            )
            if not budget.allowed:
                messages.append(
                    Message.assistant(
                        text=response.content, tool_calls=response.tool_calls, raw=response.raw
                    )
                )
                logger.info("Conversation %s stopped: %s", conversation_id, budget.reason)
                return ToolLoopResult(
                    messages=messages,
                    final_text=response.content,
                    tool_turns_used=turn,
                    stop_reason=StopReason.BUDGET_EXCEEDED,
                    stop_detail=budget.reason,
                )

            # Record the model's turn (including the calls it wants) before
            # doing anything else, so history is accurate even if execution
            # below fails.
            messages.append(
                Message.assistant(
                    text=response.content, tool_calls=response.tool_calls, raw=response.raw
                )
            )

            await self._execute_all(conversation_id, response.tool_calls, messages)

        logger.warning(
            "Tool loop hit max_tool_turns=%s for %s", self.max_tool_turns, conversation_id
        )
        return ToolLoopResult(
            messages=messages,
            final_text=None,
            tool_turns_used=self.max_tool_turns,
            stop_reason=StopReason.MAX_TOOL_TURNS,
        )

    # ------------------------------------------------------------------
    # Tool calls for one turn, run concurrently
    # ------------------------------------------------------------------

    async def _execute_all(
        self,
        conversation_id: str,
        calls: list[ToolCall],
        messages: list[Message],
    ) -> None:

        # _execute_one() catches everything it expects internally, but
        # return_exceptions=True is defense-in-depth against anything
        # that still slips through - one tool call going sideways
        # shouldn't take the rest of the turn down with it.
        raw_results = await asyncio.gather(
            *(self._execute_one(conversation_id, call) for call in calls),
            return_exceptions=True,
        )

        for call, result in zip(calls, raw_results):
            if isinstance(result, BaseException):
                logger.exception(
                    "Unexpected error executing %s", call.name, exc_info=result
                )
                messages.append(
                    Message.tool_result(
                        tool_call_id=call.id,
                        name=call.name,
                        content=f"Tool '{call.name}' failed unexpectedly: {result}",
                        is_error=True,
                    )
                )
            else:
                messages.append(result)

    # ------------------------------------------------------------------
    # One tool call: policy gate -> MCP execute -> stringify result
    # ------------------------------------------------------------------

    async def _execute_one(self, conversation_id: str, call: ToolCall) -> Message:

        decision = await self.policy.evaluate(
            conversation_id=conversation_id,
            tool_name=call.name,
            arguments=call.arguments,
        )

        if not decision.allowed:
            reason = decision.reason or "blocked by policy"
            logger.info("Blocked tool=%s reason=%s", call.name, reason)
            return Message.tool_result(
                tool_call_id=call.id,
                name=call.name,
                content=f"This tool call was blocked: {reason}",
                is_error=True,
            )

        arguments = decision.arguments if decision.arguments is not None else call.arguments

        try:
            result = await self.registry.execute(call.name, arguments)
        except KeyError:
            # Model hallucinated a tool, or a server dropped between
            # discovery and execution.
            return Message.tool_result(
                tool_call_id=call.id,
                name=call.name,
                content=f"Tool '{call.name}' is not currently available.",
                is_error=True,
            )
        except Exception as exc:
            # Covers a crashed MCP server / dropped stdio pipe / timed-out
            # transport - the model gets a clear error, the conversation
            # doesn't die. (No exception taxonomy in mcp/ yet to narrow
            # this further - see note above.)
            logger.exception("Tool execution failed for %s", call.name)
            return Message.tool_result(
                tool_call_id=call.id,
                name=call.name,
                content=f"Tool '{call.name}' failed to execute: {exc}",
                is_error=True,
            )

        text, is_error = self._stringify_result(result)
        return Message.tool_result(
            tool_call_id=call.id, name=call.name, content=text, is_error=is_error
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_tool_specs(self) -> list[ToolSpec]:
        registered = self.registry.list()
        current_key = frozenset(t.name for t in registered)

        if current_key != self._tool_spec_cache_key:
            self._tool_spec_cache = [ToolSpec.from_registered_tool(t) for t in registered]
            self._tool_spec_cache_key = current_key

        return self._tool_spec_cache

    @staticmethod
    def _stringify_result(result: Any) -> tuple[str, bool]:
        """MCP CallToolResult -> plain text, plus whether the tool itself
        reported an error (MCP's isError flag - distinct from a transport
        exception, which is caught above)."""

        is_error = bool(getattr(result, "isError", False))
        parts = getattr(result, "content", None) or []

        chunks = [
            getattr(part, "text", None) or f"[non-text content: {type(part).__name__}]"
            for part in parts
        ]
        return ("\n".join(chunks) if chunks else "(tool returned no content)"), is_error


# ----------------------------------------------------------------------
# Dev-only stub so this file is runnable before policy/engine.py exists.
# Allows everything, no budget cap.
# ----------------------------------------------------------------------

class AllowAllPolicy:
    async def evaluate(self, *, conversation_id, tool_name, arguments) -> PolicyDecision:
        return PolicyDecision(allowed=True)

    async def check_budget(self, *, conversation_id, usage: Usage) -> PolicyDecision:
        return PolicyDecision(allowed=True)