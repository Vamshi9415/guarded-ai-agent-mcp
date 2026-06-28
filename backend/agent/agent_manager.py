# backend/agent/agent_manager.py
"""AgentManager — lifecycle owner for all active Agent instances.

Responsibilities
----------------
- Create new Agent objects on demand, each with its own conversation history.
- Return an existing Agent by conversation_id for follow-up turns.
- Reset or delete conversations.
- List all active conversations with lightweight metadata.

What this class deliberately does NOT do
-----------------------------------------
- No business logic.
- No LLM calls.
- No MCP calls.
- No policy decisions.

All of those remain in Agent → ToolLoop → PolicyEngine → ToolRegistry → MCPManager,
exactly as they were before this file existed.

Sharing a single ToolLoop across all Agent instances
------------------------------------------------------
Every Agent created here receives the same ToolLoop singleton.  The ToolLoop
itself is stateless between turns — it holds no per-conversation data, only
references to the shared LLM client, ToolRegistry, and PolicyEngine.

Agent is the only object that is per-conversation (it owns the message history
and the conversation_id).  Sharing ToolLoop across agents is therefore safe and
is how run_agent.py and test_agent_scenarios.py already operate.

Thread-safety note
------------------
This class is not safe for concurrent mutations from multiple coroutines.
FastAPI's default single-threaded asyncio event loop means that awaited calls
are interleaved, never truly concurrent, so the dict operations below are safe
without a lock.  If multi-worker deployment is added later, replace
``_agents`` with a proper shared store (Redis, etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Callable
from typing import Iterator

from backend.agent.agent import Agent
from backend.agent.tool_loop import ToolLoop

logger = logging.getLogger(__name__)


@dataclass
class ConversationMeta:
    """Lightweight metadata stored alongside each active Agent.

    Kept separate from Agent itself so Agent remains unaware of any
    management layer on top of it.
    """

    conversation_id: str
    created_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    message_count: int = 0

    def refresh_message_count(self, agent: Agent) -> None:
        """Syncs message_count from the agent's current history.

        The system prompt counts as the first message, so subtract 1 to
        report only the user/assistant turns visible to the caller.
        """
        self.message_count = sum(1 for message in agent.messages if message.role == "user")


class AgentManager:
    """Creates, retrieves, and destroys Agent instances.

    One AgentManager lives for the lifetime of the FastAPI process (it is a
    singleton via the dependency provider).  It wraps a single shared ToolLoop
    so every conversation reuses the same LLM client, ToolRegistry, and
    PolicyEngine, while each conversation gets its own Agent (and thus its own
    isolated message history).

    Args:
        tool_loop: The shared ToolLoop instance injected once at startup.
            Every Agent created by this manager will delegate its execution to
            this same ToolLoop.
    """

    def __init__(self, tool_loop: ToolLoop | Callable[[], ToolLoop]) -> None:
        self._tool_loop = tool_loop
        # Keyed by conversation_id — insertion-ordered in Python 3.7+.
        self._agents: dict[str, Agent] = {}
        self._meta: dict[str, ConversationMeta] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def create(self, conversation_id: str | None = None) -> Agent:
        """Creates a new Agent and registers it in the active-conversation table.

        If ``conversation_id`` is supplied and already exists, the existing
        Agent is returned unchanged (idempotent — callers that generate a UUID
        before calling ``create`` will not accidentally overwrite an active
        conversation).

        Args:
            conversation_id: Optional stable identifier for the conversation.
                When omitted, Agent generates a UUID internally; that ID is
                then read back and stored here.

        Returns:
            The newly created (or already-existing) Agent.
        """
        if conversation_id and conversation_id in self._agents:
            logger.debug("create() called for existing conversation %s — returning existing agent", conversation_id)
            return self._agents[conversation_id]

        agent = Agent(tool_loop=self._resolve_tool_loop(), conversation_id=conversation_id)
        cid = agent.conversation_id   # read back in case Agent generated it

        self._agents[cid] = agent
        self._meta[cid] = ConversationMeta(conversation_id=cid)

        logger.info("Created new conversation %s (total active: %d)", cid, len(self._agents))
        return agent

    def get(self, conversation_id: str) -> Agent:
        """Returns the Agent for an existing conversation.

        Raises:
            KeyError: If no active conversation with that id exists.
                The global exception handler converts this to HTTP 404.
        """
        try:
            return self._agents[conversation_id]
        except KeyError:
            raise KeyError(f"Conversation '{conversation_id}' not found") from None

    def get_or_create(self, conversation_id: str | None) -> Agent:
        """Returns an existing Agent or creates a new one.

        This is the main path for ``POST /api/chat``:
        - ``conversation_id`` is None → create fresh conversation.
        - ``conversation_id`` is known → return that conversation.
        - ``conversation_id`` is unrecognised → raise KeyError (404).

        Args:
            conversation_id: The id from the request body, or None for new.

        Returns:
            The resolved Agent.

        Raises:
            KeyError: If a non-None conversation_id is not found.
        """
        if conversation_id is None:
            return self.create()
        return self.get(conversation_id)

    def reset(self, conversation_id: str) -> Agent:
        """Clears a conversation's history back to the system prompt.

        The conversation_id and created_at timestamp are preserved.
        message_count is reset to zero.

        Args:
            conversation_id: The conversation to reset.

        Returns:
            The same Agent with a cleared history.

        Raises:
            KeyError: If the conversation does not exist.
        """
        agent = self.get(conversation_id)
        agent.reset()
        self._meta[conversation_id].message_count = 0
        logger.info("Reset conversation %s", conversation_id)
        return agent

    def delete(self, conversation_id: str) -> None:
        """Removes a conversation and its Agent from the active table.

        Args:
            conversation_id: The conversation to delete.

        Raises:
            KeyError: If the conversation does not exist.
        """
        self.get(conversation_id)   # raises KeyError if missing
        del self._agents[conversation_id]
        del self._meta[conversation_id]
        logger.info("Deleted conversation %s (total active: %d)", conversation_id, len(self._agents))

    def list_conversations(self) -> list[ConversationMeta]:
        """Returns metadata for all active conversations, oldest first."""
        for cid, meta in self._meta.items():
            meta.refresh_message_count(self._agents[cid])
        return list(self._meta.values())

    def update_meta(self, conversation_id: str) -> None:
        """Refreshes the message_count for one conversation after a chat turn.

        Called by the chat router after agent.chat() returns so that
        list_conversations() reports up-to-date counts.
        """
        if conversation_id in self._meta:
            self._meta[conversation_id].refresh_message_count(
                self._agents[conversation_id]
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_tool_loop(self) -> ToolLoop:
        if hasattr(self._tool_loop, "run"):
            return self._tool_loop
        return self._tool_loop()
    
    def __len__(self) -> int:
        return len(self._agents)

    def __iter__(self) -> Iterator[str]:
        return iter(self._agents)





