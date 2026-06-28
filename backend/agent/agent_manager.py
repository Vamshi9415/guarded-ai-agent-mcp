# backend/agent/agent_manager.py
"""AgentManager — lifecycle owner for active Agent instances and chat persistence.

The in-memory Agent cache remains the fast path for currently active
conversations, but the source of truth for conversation history is the chat
store injected here. That lets the API reload old conversations after a page
refresh or process restart instead of dropping back to an empty window.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Iterator

from backend.agent.agent import Agent
from backend.agent.chat_store import ChatStore, ConversationTranscript, InMemoryChatStore
from backend.agent.tool_loop import ToolLoop
from backend.llm.base import Message

logger = logging.getLogger(__name__)


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

    def __init__(
        self,
        tool_loop: ToolLoop | Callable[[], ToolLoop],
        chat_store: ChatStore | None = None,
    ) -> None:
        self._tool_loop = tool_loop
        self._chat_store = chat_store or InMemoryChatStore()
        # Keyed by conversation_id — insertion-ordered in Python 3.7+.
        self._agents: dict[str, Agent] = {}

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

        transcript = None
        if conversation_id is not None:
            try:
                transcript = self._chat_store.get_conversation(conversation_id)
            except KeyError:
                transcript = None

        agent = Agent(
            tool_loop=self._resolve_tool_loop(),
            conversation_id=conversation_id,
            messages=list(transcript.messages) if transcript is not None else None,
        )
        cid = agent.conversation_id   # read back in case Agent generated it

        self._agents[cid] = agent

        logger.info("Created new conversation %s (total active: %d)", cid, len(self._agents))
        return agent

    def get(self, conversation_id: str) -> Agent:
        """Returns the Agent for an existing conversation.

        Raises:
            KeyError: If no active conversation with that id exists.
                The global exception handler converts this to HTTP 404.
        """
        agent = self._agents.get(conversation_id)
        if agent is not None:
            return agent

        try:
            transcript = self._chat_store.get_conversation(conversation_id)
        except KeyError:
            raise KeyError(f"Conversation '{conversation_id}' not found") from None

        agent = Agent(
            tool_loop=self._resolve_tool_loop(),
            conversation_id=conversation_id,
            messages=list(transcript.messages),
        )
        self._agents[conversation_id] = agent
        return agent

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
        self._save_agent(agent)
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
        self._chat_store.delete_conversation(conversation_id)
        logger.info("Deleted conversation %s (total active: %d)", conversation_id, len(self._agents))

    def list_conversations(self) -> list[ConversationTranscript]:
        """Returns persisted conversation metadata, oldest first."""
        return self._chat_store.list_conversations()

    def save(self, conversation_id: str) -> None:
        """Persists the latest in-memory transcript for one conversation."""
        agent = self.get(conversation_id)
        self._save_agent(agent)

    def get_messages(self, conversation_id: str) -> tuple["Message", ...]:
        agent = self._agents.get(conversation_id)
        if agent is not None:
            return agent.messages
        transcript = self._chat_store.get_conversation(conversation_id)
        return tuple(transcript.messages)

    def get_transcript(self, conversation_id: str) -> ConversationTranscript:
        agent = self._agents.get(conversation_id)
        if agent is not None:
            try:
                existing = self._chat_store.get_conversation(conversation_id)
                created_at = existing.created_at
            except KeyError:
                created_at = ConversationTranscript(conversation_id=conversation_id).created_at
            return ConversationTranscript(
                conversation_id=conversation_id,
                created_at=created_at,
                messages=list(agent.messages),
            )
        return self._chat_store.get_conversation(conversation_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_tool_loop(self) -> ToolLoop:
        if hasattr(self._tool_loop, "run"):
            return self._tool_loop
        return self._tool_loop()

    def _save_agent(self, agent: Agent) -> None:
        try:
            existing = self._chat_store.get_conversation(agent.conversation_id)
            created_at = existing.created_at
        except KeyError:
            created_at = ConversationTranscript(conversation_id=agent.conversation_id).created_at

        self._chat_store.save_conversation(
            ConversationTranscript(
                conversation_id=agent.conversation_id,
                created_at=created_at,
                messages=list(agent.messages),
            )
        )

    def __len__(self) -> int:
        return len(self._agents)

    def __iter__(self) -> Iterator[str]:
        return iter(self._agents)





