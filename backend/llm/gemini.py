# backend/llm/gemini.py

from __future__ import annotations

import logging
import os
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .base import BaseLLMClient,LLMError,LLMResponse,Message,ToolCall,ToolSpec,Usage

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"

#sanitize acc to gemini doc 
_UNSUPPORTED_SCHEMA_KEYS = {"$schema", "additionalProperties", "title"}


def _sanitize_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema

    cleaned = {k: v for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_KEYS}

    if isinstance(cleaned.get("properties"), dict):
        cleaned["properties"] = {
            name: _sanitize_schema(prop) for name, prop in cleaned["properties"].items()
        }
    if "items" in cleaned:
        cleaned["items"] = _sanitize_schema(cleaned["items"])

    return cleaned

class GeminiLLM(BaseLLMClient):
    def __init__(self,api_key = None,model = None, system_instr = None):
        api_key = api_key or os.getenv("GEMINI_API_KEY") 
        self.model = model or DEFAULT_MODEL 
        self.system_instruction = system_instr 
        
        if not api_key :
            raise ValueError("No Gemini APi key found")
        
        self.client = genai.Client(api_key=api_key)
    
    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:

        contents, system_instruction = self._build_contents(messages)

        config_kwargs: dict[str, Any] = {}

        if system_instruction or self.system_instruction:
            config_kwargs["system_instruction"] = system_instruction or self.system_instruction

        if tools:
            config_kwargs["tools"] = [self._build_tool(tools)]
            # Never let the SDK call real Python functions on our behalf -
            # the policy engine has to see and approve every call first.
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except genai_errors.APIError as exc:
            logger.exception("Gemini request failed")
            raise LLMError(f"Gemini request failed: {exc}") from exc

        return self._parse_response(response)

    async def close(self) -> None:
        await self.client.aio.aclose()

    # ------------------------------------------------------------------
    # generic -> Gemini
    # ------------------------------------------------------------------

    def _build_tool(self, tools: list[ToolSpec]) -> types.Tool:
        declarations = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=_sanitize_schema(tool.parameters),
            )
            for tool in tools
        ]
        return types.Tool(function_declarations=declarations)

    def _build_contents(
        self, messages: list[Message]
    ) -> tuple[list[types.Content], str | None]:

        contents: list[types.Content] = []
        system_instruction: str | None = None

        for message in messages:

            if message.role == "system":
                # Gemini takes system prompts out-of-band, not as a turn.
                system_instruction = (
                    f"{system_instruction}\n{message.content}".strip()
                    if system_instruction else message.content
                )
                continue

            if message.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message.content or "")],
                    )
                )
                continue

            if message.role == "assistant":
                # Prefer replaying the SDK's own Content object - it carries
                # thought signatures the model needs to stay coherent across
                # a multi-step tool call. We stash this on LLMResponse.raw;
                # tool_loop.py should pass it straight into Message.assistant(raw=...).
                if message.raw is not None:
                    contents.append(message.raw)
                    continue

                parts = []
                if message.content:
                    parts.append(types.Part.from_text(text=message.content))
                for call in message.tool_calls:
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                id=call.id, name=call.name, args=call.arguments
                            )
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
                continue

            if message.role == "tool":
                response_payload = (
                    {"error": message.content} if message.is_error
                    else {"result": message.content}
                )
                contents.append(
                    types.Content(
                        role="tool",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    id=message.tool_call_id,
                                    name=message.name,
                                    response=response_payload,
                                )
                            )
                        ],
                    )
                )
                continue

        return contents, system_instruction

    # ------------------------------------------------------------------
    # Gemini -> generic
    # ------------------------------------------------------------------

    def _parse_response(self, response: Any) -> LLMResponse:

        candidate = response.candidates[0] if response.candidates else None
        content = candidate.content if candidate else None

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        if content and content.parts:
            for part in content.parts:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    tool_calls.append(
                        ToolCall(
                            id=fc.id or ToolCall.new_id(),
                            name=fc.name,
                            arguments=dict(fc.args or {}),
                        )
                    )

        usage_meta = getattr(response, "usage_metadata", None)
        usage = Usage(
            input_tokens=getattr(usage_meta, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage_meta, "candidates_token_count", 0) or 0,
        )

        return LLMResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=str(getattr(candidate, "finish_reason", None)) if candidate else None,
            raw=content,
        )


GeminiClient = GeminiLLM

