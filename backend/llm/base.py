from __future__ import annotations 

from abc import ABC, abstractmethod 

from dataclasses import dataclass, field
from typing import Any, Literal 

import uuid
Role = Literal["system","user","assistant","tool"]

class LLMError(Exception):
    """ just an error class for when llm provider call fails"""

@dataclass
class ToolCall :
    id :str
    name : str 
    arguments : dict[str,Any]

    @property
    def args(self) -> dict[str, Any]:
        return self.arguments
    
    @staticmethod
    def new_id() ->str :
        return uuid.uuid4().hex[:12]
    

@dataclass
class Message:
    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None   
    name: str | None = None          
    is_error: bool = False            
    raw: Any = None                 

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role="user", content=text)

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(role="system", content=text)

    @classmethod
    def assistant(
        cls,
        text: str | None = None,
        tool_calls: list[ToolCall] | None = None,
        raw: Any = None,
    ) -> "Message":
        return cls(role="assistant", content=text, tool_calls=tool_calls or [], raw=raw)

    @classmethod
    def tool_result(
        cls,
        tool_call_id: str,
        name: str,
        content: str,
        is_error: bool = False,
    ) -> "Message":
        return cls(
            role="tool",
            tool_call_id=tool_call_id,
            name=name,
            content=content,
            is_error=is_error,
        )


@dataclass
class ToolSpec:
    """Provider-agnostic description of a tool, built straight from an
    MCP RegisteredTool. This is the seam between mcp/registry.py and
    whatever LLM client is in use."""
    name: str
    description: str
    parameters: dict[str, Any]

    @classmethod 
    def from_registered_tool(cls, tool: Any) -> "ToolSpec":
        return cls(
            name=tool.name,
            description=tool.description or "",
            parameters=tool.input_schema or {"type": "object", "properties": {}},
        )


# backend/llm/base.py  — add an __add__ to Usage
@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: Usage
    finish_reason: str | None = None
    raw: Any = None  # stash the provider's native turn for replay next call

    @property
    def wants_tool_call(self) -> bool:
        return bool(self.tool_calls)


class BaseLLMClient(ABC):

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        """
        Send the full conversation so far (+ available tools) and get back
        ONE response: text, or one/more tool calls to run next. The caller
        (tool_loop.py) owns the loop - this never loops or executes a tool
        itself, and never decides whether a call is *allowed*. That's the
        policy engine's job, one layer up.
        """
        raise NotImplementedError

    async def close(self) -> None:
        return None





