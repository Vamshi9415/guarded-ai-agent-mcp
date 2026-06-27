# backend/llm/gemini.py
from __future__ import annotations

import itertools
import logging
import os
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .base import BaseLLMClient, LLMError, LLMResponse, Message, ToolCall, ToolSpec, Usage

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"

# Keys Gemini's schema validator rejects - strip them before sending.
UNSUPPORTED_SCHEMA_KEYS = {"$schema", "additionalProperties", "title"}


def sanitize_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema
    cleaned = {k: v for k, v in schema.items() if k not in UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(cleaned.get("properties"), dict):
        cleaned["properties"] = {
            name: sanitize_schema(prop)
            for name, prop in cleaned["properties"].items()
        }
    if "items" in cleaned:
        cleaned["items"] = sanitize_schema(cleaned["items"])
    return cleaned


# -------------------------------------------------------------------------
# Round-robin API key manager
# -------------------------------------------------------------------------

class RoundRobinKeyManager:
    """
    Cycles through a list of Gemini API keys in round-robin order.

    Construction:
        manager = RoundRobinKeyManager()           # reads env vars automatically
        manager = RoundRobinKeyManager(["k1","k2"]) # explicit list

    Environment variable resolution (in priority order):
        1. GEMINI_API_KEY_1, GEMINI_API_KEY_2, ... GEMINI_API_KEY_N
        2. GEMINI_API_KEYS  (comma-separated: "k1,k2,k3")
        3. GEMINI_API_KEY   (single key fallback)

    Usage:
        key = manager.current()    # peek without advancing
        key = manager.next()       # advance and return next key
        manager.mark_exhausted(k)  # called on 429 - rotate away from this key
    """

    def __init__(self, keys: list[str] | None = None) -> None:
        if keys:
            resolved = [k.strip() for k in keys if k.strip()]
        else:
            resolved = self._resolve_from_env()

        if not resolved:
            raise ValueError(
                "No Gemini API keys found. Set GEMINI_API_KEY, "
                "GEMINI_API_KEYS (comma-separated), or "
                "GEMINI_API_KEY_1 / GEMINI_API_KEY_2 / ... in your environment."
            )

        self._keys: list[str] = resolved
        self._cycle = itertools.cycle(self._keys)
        self._current: str = next(self._cycle)

        logger.info(
            "RoundRobinKeyManager initialised with %d key(s): [%s]",
            len(self._keys),
            ", ".join(f"...{k[-4:]}" for k in self._keys),  # log only last 4 chars
        )

    # ------------------------------------------------------------------
    # Key resolution helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_from_env() -> list[str]:
        """
        Tries three env-var conventions in order:
          1. GEMINI_API_KEY_1 … GEMINI_API_KEY_N   (numbered, stops at first gap)
          2. GEMINI_API_KEYS                        (comma-separated single var)
          3. GEMINI_API_KEY                         (plain single key)
        Returns a deduplicated list preserving order.
        """
        seen: set[str] = set()
        keys: list[str] = []

        def _add(k: str) -> None:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)

        # 1. Numbered vars
        idx = 1
        while True:
            val = os.getenv(f"GEMINI_API_KEY_{idx}")
            if not val:
                break
            _add(val)
            idx += 1

        # 2. Comma-separated var
        multi = os.getenv("GEMINI_API_KEYS", "")
        for part in multi.split(","):
            _add(part)

        # 3. Plain single var
        single = os.getenv("GEMINI_API_KEY", "")
        _add(single)

        return keys

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self._keys)

    def current(self) -> str:
        """Return the currently active key without advancing the cycle."""
        return self._current

    def next(self) -> str:
        """Advance the cycle and return the next key."""
        self._current = next(self._cycle)
        return self._current

    def mark_exhausted(self, key: str) -> str:
        """
        Called when `key` returned a 429 / quota error.
        Rotates to the next key immediately and returns it.
        Logs a warning so operators can see quota pressure.
        """
        logger.warning(
            "Key ...%s hit quota/rate-limit - rotating to next key.", key[-4:]
        )
        return self.next()


# -------------------------------------------------------------------------
# Gemini LLM client with round-robin key rotation
# -------------------------------------------------------------------------

class GeminiLLM(BaseLLMClient):
    """
    Gemini client that rotates across multiple API keys in round-robin order.

    On each call to generate():
      - Uses the current key.
      - On 429 / ResourceExhausted: rotates to the next key and retries.
        Retries at most len(keys) times (one full cycle) before giving up,
        so a total quota exhaustion across all keys raises LLMError cleanly
        rather than looping forever.
      - On any other API error: raises LLMError immediately (no retry).
    """

    def __init__(
        self,
        keys: list[str] | None = None,
        model: str | None = None,
        system_instr: str | None = None,
    ) -> None:
        self._key_manager = RoundRobinKeyManager(keys)
        self.model = model or DEFAULT_MODEL
        self.system_instruction = system_instr
        # One genai.Client per key, built lazily and cached.
        self._clients: dict[str, genai.Client] = {}

    def _client_for(self, key: str) -> genai.Client:
        """Return (or create and cache) a genai.Client for the given key."""
        if key not in self._clients:
            self._clients[key] = genai.Client(api_key=key)
        return self._clients[key]

    # async def generate(
    #     self,
    #     messages: list[Message],
    #     tools: list[ToolSpec] | None = None,
    # ) -> LLMResponse:
    #     contents, system_instruction = self._build_contents(messages)

    #     config_kwargs: dict[str, Any] = {}
    #     if system_instruction or self.system_instruction:
    #         config_kwargs["system_instruction"] = system_instruction or self.system_instruction
    #     if tools:
    #         config_kwargs["tools"] = self._build_tool(tools)
    #         config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
    #             disable=True
    #         )
    #     config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    #     # Retry loop: try each key at most once per generate() call.
    #     max_attempts = self._key_manager.count
    #     last_error: Exception | None = None

    #     for attempt in range(max_attempts):
    #         key = self._key_manager.current()
    #         client = self._client_for(key)

    #         try:
    #             response = await client.aio.models.generate_content(
    #                 model=self.model,
    #                 contents=contents,
    #                 config=config,
    #             )
    #             logger.debug(
    #                 "generate() succeeded on attempt %d with key ...%s",
    #                 attempt + 1, key[-4:]
    #             )
    #             return self._parse_response(response)

    #         except genai_errors.APIError as exc:
    #             # 429 or ResourceExhausted → rotate and retry with next key
    #             status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    #             is_quota = status == 429 or "ResourceExhausted" in type(exc).__name__

    #             if is_quota and attempt < max_attempts - 1:
    #                 next_key = self._key_manager.mark_exhausted(key)
    #                 logger.info(
    #                     "Rotated from key ...%s to ...%s (attempt %d/%d)",
    #                     key[-4:], next_key[-4:], attempt + 1, max_attempts,
    #                 )
    #                 last_error = exc
    #                 continue  # retry with next key

    #             # Non-quota error, or all keys exhausted
    #             logger.exception("Gemini request failed (key ...%s)", key[-4:])
    #             raise LLMError(f"Gemini request failed: {exc}") from exc

    #     # All keys returned 429 - surface a clean error
    #     raise LLMError(
    #         f"All {max_attempts} Gemini API key(s) are rate-limited. "
    #         f"Last error: {last_error}"
    #     )
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
            config_kwargs["automatic_function_calling"] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
    
        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
    
        max_attempts = self._key_manager.count
        last_error: Exception | None = None
    
        for attempt in range(max_attempts):
            key = self._key_manager.current()
            client = self._client_for(key)
    
            try:
                response = await client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )
                return self._parse_response(response)
    
            except genai_errors.APIError as exc:
                status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                is_quota = status == 429 or "ResourceExhausted" in type(exc).__name__
    
                if is_quota and attempt < max_attempts - 1:
                    self._key_manager.mark_exhausted(key)
                    last_error = exc
                    continue
                
                raise LLMError(f"Gemini request failed: {exc}") from exc
    
        raise LLMError(
            f"All {max_attempts} Gemini API key(s) are rate-limited. Last error: {last_error}"
        )
    async def close(self) -> None:
        for client in self._clients.values():
            await client.aio.aclose()
        self._clients.clear()

    # ------------------------------------------------------------------
    # Gemini-specific helpers (unchanged from original)
    # ------------------------------------------------------------------

    def _build_tool(self, tools: list[ToolSpec]) -> types.Tool:
        declarations = [
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=sanitize_schema(tool.parameters),  # type: ignore[arg-type]
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
                system_instruction = (
                    f"{system_instruction}\n{message.content}".strip()
                    if system_instruction
                    else message.content
                )
                continue

            if message.role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=message.content or "")])
                )
                continue

            if message.role == "assistant":
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
                    {"error": message.content} if message.is_error else {"result": message.content}
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
            content="".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=str(getattr(candidate, "finish_reason", None)) if candidate else None,
            raw=content,
        )


# Public alias - all other modules import GeminiClient, not GeminiLLM
GeminiClient = GeminiLLM