"""Persistence for chat conversation transcripts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from pymongo import ASCENDING
from pymongo.collection import Collection

from backend.llm.base import Message, ToolCall
from backend.policy.mongo_connection import MongoSettings, create_mongo_client


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _tool_call_to_doc(tool_call: ToolCall) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "name": tool_call.name,
        "arguments": deepcopy(tool_call.arguments),
    }


def _tool_call_from_doc(doc: dict[str, Any]) -> ToolCall:
    return ToolCall(
        id=doc["id"],
        name=doc["name"],
        arguments=deepcopy(doc.get("arguments", {})),
    )


def _message_to_doc(message: Message) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "tool_calls": [_tool_call_to_doc(item) for item in message.tool_calls],
        "tool_call_id": message.tool_call_id,
        "name": message.name,
        "is_error": message.is_error,
    }


def _message_from_doc(doc: dict[str, Any]) -> Message:
    return Message(
        role=doc["role"],
        content=doc.get("content"),
        tool_calls=[_tool_call_from_doc(item) for item in doc.get("tool_calls", [])],
        tool_call_id=doc.get("tool_call_id"),
        name=doc.get("name"),
        is_error=bool(doc.get("is_error", False)),
    )


def _message_count(messages: list[Message]) -> int:
    return sum(1 for message in messages if message.role == "user")


@dataclass
class ConversationTranscript:
    conversation_id: str
    created_at: datetime = field(default_factory=_utcnow)
    messages: list[Message] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return _message_count(self.messages)


@runtime_checkable
class ChatStore(Protocol):
    def get_conversation(self, conversation_id: str) -> ConversationTranscript:
        ...

    def save_conversation(self, transcript: ConversationTranscript) -> ConversationTranscript:
        ...

    def list_conversations(self) -> list[ConversationTranscript]:
        ...

    def delete_conversation(self, conversation_id: str) -> None:
        ...

    def close(self) -> None:
        ...


class InMemoryChatStore(ChatStore):
    def __init__(self) -> None:
        self._conversations: dict[str, ConversationTranscript] = {}

    def get_conversation(self, conversation_id: str) -> ConversationTranscript:
        transcript = self._conversations.get(conversation_id)
        if transcript is None:
            raise KeyError(f"Conversation '{conversation_id}' not found")
        return ConversationTranscript(
            conversation_id=transcript.conversation_id,
            created_at=transcript.created_at,
            messages=deepcopy(transcript.messages),
        )

    def save_conversation(self, transcript: ConversationTranscript) -> ConversationTranscript:
        stored = ConversationTranscript(
            conversation_id=transcript.conversation_id,
            created_at=transcript.created_at,
            messages=deepcopy(transcript.messages),
        )
        self._conversations[stored.conversation_id] = stored
        return self.get_conversation(stored.conversation_id)

    def list_conversations(self) -> list[ConversationTranscript]:
        transcripts = sorted(self._conversations.values(), key=lambda item: item.created_at)
        return [
            ConversationTranscript(
                conversation_id=transcript.conversation_id,
                created_at=transcript.created_at,
                messages=deepcopy(transcript.messages),
            )
            for transcript in transcripts
        ]

    def delete_conversation(self, conversation_id: str) -> None:
        if conversation_id not in self._conversations:
            raise KeyError(f"Conversation '{conversation_id}' not found")
        del self._conversations[conversation_id]

    def close(self) -> None:
        return None


class MongoChatStore(ChatStore):
    def __init__(self) -> None:
        settings = MongoSettings.from_env()
        client = create_mongo_client()
        db_name = settings.db_name
        self._client = client
        self._collection: Collection = client[db_name]["chat_conversations"]
        self._collection.create_index([("conversation_id", ASCENDING)], unique=True)

    def get_conversation(self, conversation_id: str) -> ConversationTranscript:
        doc = self._collection.find_one({"conversation_id": conversation_id})
        if doc is None:
            raise KeyError(f"Conversation '{conversation_id}' not found")
        return ConversationTranscript(
            conversation_id=doc["conversation_id"],
            created_at=doc.get("created_at", _utcnow()),
            messages=[_message_from_doc(item) for item in doc.get("messages", [])],
        )

    def save_conversation(self, transcript: ConversationTranscript) -> ConversationTranscript:
        existing = self._collection.find_one({"conversation_id": transcript.conversation_id})
        created_at = existing.get("created_at") if existing else transcript.created_at
        self._collection.update_one(
            {"conversation_id": transcript.conversation_id},
            {
                "$set": {
                    "conversation_id": transcript.conversation_id,
                    "created_at": created_at,
                    "updated_at": _utcnow(),
                    "message_count": transcript.message_count,
                    "messages": [_message_to_doc(item) for item in transcript.messages],
                }
            },
            upsert=True,
        )
        return self.get_conversation(transcript.conversation_id)

    def list_conversations(self) -> list[ConversationTranscript]:
        docs = self._collection.find().sort("created_at", ASCENDING)
        return [
            ConversationTranscript(
                conversation_id=doc["conversation_id"],
                created_at=doc.get("created_at", _utcnow()),
                messages=[_message_from_doc(item) for item in doc.get("messages", [])],
            )
            for doc in docs
        ]

    def delete_conversation(self, conversation_id: str) -> None:
        result = self._collection.delete_one({"conversation_id": conversation_id})
        if result.deleted_count == 0:
            raise KeyError(f"Conversation '{conversation_id}' not found")

    def close(self) -> None:
        self._client.close()
