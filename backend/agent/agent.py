# backend/agent/agent.py

from __future__ import annotations

import uuid

from ..llm.base import Message
from .tool_loop import ToolLoop


class Agent:

    def __init__(self, tool_loop: ToolLoop):
        self.tool_loop = tool_loop

    async def chat(self, prompt: str):

        conversation = [
            Message.system(
                """You are an AI assistant with access to external tools.

Whenever a user's request can be fulfilled using one of the available tools,
you MUST call the appropriate tool instead of answering from your own knowledge.

Never claim that you cannot perform an action if a suitable tool exists.

If a tool exists for CRUD operations, always use it."""
            ),
            Message.user(prompt),
        ]

        result = await self.tool_loop.run(
            conversation,
            conversation_id=uuid.uuid4().hex,
        )

        return result.final_text