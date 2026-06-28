# backend/api/schemas_chat.py
"""Chat-specific Pydantic schemas.

Kept in a separate file so the growing schemas.py stays focused on
policy-layer models (rules, approvals, budgets, logs).

These schemas cover the two new surface areas:
  - POST /api/chat            → ChatRequest / ChatResponse
  - GET  /api/chat/conversations → ConversationSummary
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.api.schemas import APIModel


class ChatRequest(APIModel):
    """Request body for POST /api/chat.

    Fields
    ------
    conversation_id
        Optional.  When None, the backend creates a fresh conversation and
        returns its newly generated id in ChatResponse.  When provided, the
        message is appended to the existing conversation.

    message
        The user's message text.  Must be at least one character so the agent
        is never called with an empty string (which would waste an API call and
        produce a confusing reply).
    """

    conversation_id: str | None = Field(
        default=None,
        description=(
            "Existing conversation to continue, or null to start a new one."
        ),
    )
    message: str = Field(
        min_length=1,
        description="The user's message.",
    )


class ChatResponse(APIModel):
    """Response body for POST /api/chat.

    Fields
    ------
    conversation_id
        The stable id for this conversation.  Always present — callers that
        sent conversation_id=null should store this value and include it in
        subsequent requests to continue the same conversation.

    reply
        The agent's reply text.  Never null — Agent.chat() guarantees a
        non-empty string even when the tool loop hits its turn cap or budget
        limit (it returns a descriptive fallback message in those cases).
    """

    conversation_id: str
    reply: str


class ChatMessage(APIModel):
    """One visible message in a conversation transcript."""

    role: Literal["user", "assistant"]
    content: str


class ConversationTranscript(APIModel):
    """Full conversation transcript returned to the chat UI."""

    conversation_id: str
    created_at: datetime
    message_count: int
    messages: list[ChatMessage]


class ConversationSummary(APIModel):
    """One entry in GET /api/chat/conversations.

    Fields
    ------
    conversation_id
        Stable identifier for the conversation.

    created_at
        When the conversation was first created (UTC).

    message_count
        Number of user/assistant turns (excludes the system prompt).
        Updated after every chat turn.
    """

    conversation_id: str
    created_at: datetime
    message_count: int