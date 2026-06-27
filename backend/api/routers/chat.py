# backend/api/routers/chat.py
"""Chat API routes — the thin FastAPI surface over the existing Agent.

Execution flow for POST /api/chat
----------------------------------
  FastAPI
      ↓  (validates ChatRequest via Pydantic)
  AgentManager.get_or_create(conversation_id)
      ↓  (returns or creates an Agent)
  agent.chat(message)
      ↓
  ToolLoop.run(messages, conversation_id)
      ↓
  PolicyEngine.evaluate / check_budget
      ↓
  ToolRegistry.execute
      ↓
  MCPManager → MCP servers
      ↓
  ChatResponse

FastAPI never touches the LLM, MCP, or PolicyEngine directly.  All
business logic lives in the layers below.

Conversation management endpoints
-----------------------------------
  GET  /api/chat/conversations          — list active conversations
  POST /api/chat/{conversation_id}/reset — clear history for one conversation
  DELETE /api/chat/{conversation_id}    — delete a conversation
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Response, status

from backend.agent.agent_manager import AgentManager
from backend.api.dependencies import get_agent_manager
from backend.api.schemas_chat import ChatRequest, ChatResponse, ConversationSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    manager: AgentManager = Depends(get_agent_manager),
) -> ChatResponse:
    """Sends a message to the agent and returns its reply.

    If ``conversation_id`` is null, a new conversation is created and its id
    is included in the response.  Subsequent requests should pass that id to
    continue the same conversation.

    If ``conversation_id`` is provided but not found, the global KeyError
    handler returns HTTP 404 — no local try/except needed here.
    """
    agent = manager.get_or_create(payload.conversation_id)
    cid = agent.conversation_id

    logger.info(
        "Chat request | conversation=%s | message_length=%d",
        cid,
        len(payload.message),
    )

    t0 = time.perf_counter()
    reply = await agent.chat(payload.message)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    manager.update_meta(cid)

    logger.info(
        "Chat reply   | conversation=%s | reply_length=%d | duration_ms=%.1f",
        cid,
        len(reply),
        elapsed_ms,
    )

    return ChatResponse(conversation_id=cid, reply=reply)


# ---------------------------------------------------------------------------
# GET /api/chat/conversations
# ---------------------------------------------------------------------------

@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    manager: AgentManager = Depends(get_agent_manager),
) -> list[ConversationSummary]:
    """Returns metadata for all active conversations, oldest first.

    ``message_count`` reflects the number of user/assistant turns (the system
    prompt is excluded from the count).
    """
    metas = manager.list_conversations()
    return [
        ConversationSummary(
            conversation_id=meta.conversation_id,
            created_at=meta.created_at,
            message_count=meta.message_count,
        )
        for meta in metas
    ]


# ---------------------------------------------------------------------------
# POST /api/chat/{conversation_id}/reset
# ---------------------------------------------------------------------------

@router.post("/{conversation_id}/reset", response_model=ConversationSummary)
async def reset_conversation(
    conversation_id: str,
    manager: AgentManager = Depends(get_agent_manager),
) -> ConversationSummary:
    """Clears the history for one conversation back to the system prompt.

    The conversation_id and created_at are preserved.  Returns the updated
    ConversationSummary so callers can confirm message_count is now 0.

    HTTP 404 if the conversation does not exist (raised by AgentManager.get
    → global KeyError handler).
    """
    manager.reset(conversation_id)
    meta = next(
        m for m in manager.list_conversations()
        if m.conversation_id == conversation_id
    )
    logger.info("Reset conversation %s via API", conversation_id)
    return ConversationSummary(
        conversation_id=meta.conversation_id,
        created_at=meta.created_at,
        message_count=meta.message_count,
    )


# ---------------------------------------------------------------------------
# DELETE /api/chat/{conversation_id}
# ---------------------------------------------------------------------------

@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    manager: AgentManager = Depends(get_agent_manager),
) -> Response:
    """Deletes a conversation and its Agent.

    HTTP 404 if the conversation does not exist (raised by AgentManager.delete
    → global KeyError handler).
    """
    manager.delete(conversation_id)
    logger.info("Deleted conversation %s via API", conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)