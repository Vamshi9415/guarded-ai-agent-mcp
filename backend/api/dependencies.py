# backend/api/dependencies.py
"""Dependency providers for the FastAPI admin backend.

This module is the only place in the API layer that owns long-lived
dependency instances.  Routers obtain everything through FastAPI's dependency
injection so the API surface stays thin and the underlying components remain
easily swappable.

Startup / shutdown wiring
--------------------------
MCPManager and GeminiClient require async lifecycle management
(connect_all / disconnect_all, close).  That lifecycle is owned by the
lifespan context manager in app.py, which calls the ``startup()`` and
``shutdown()`` helpers defined here so that the same singleton instances used
by the dependency providers are the ones that get connected and closed.

Dependency graph
----------------
get_policy_store()
    └─ get_approval_manager()
           └─ get_policy_engine()
                      └─ get_tool_loop()
                                └─ get_agent_manager()
"""

from __future__ import annotations

import os
import sys
import logging
from functools import lru_cache
from pathlib import Path

from backend.agent.agent_manager import AgentManager
from backend.agent.chat_store import MongoChatStore
from backend.agent.tool_loop import ToolLoop
from backend.llm.gemini import GeminiClient
from backend.mcp.manager import MCPManager
from backend.mcp.registry import ToolRegistry
from backend.mcp.transport.stdio_transport import StdioTransport
from backend.mcp.transport.streamble_http_transport import StreamableHTTPTransport
from backend.policy.approvals import ApprovalManager
from backend.policy.engine import PolicyEngine
from backend.policy.mongo_store import MongoPolicyStore
from backend.policy.store import PolicyStore

logger = logging.getLogger(__name__)

# Path to the local MCP server script — same resolution as run_agent.py.
_MCP_SERVER_PATH = Path(__file__).parent.parent / "mcp" / "server.py"


# ---------------------------------------------------------------------------
# Policy layer — identical pattern to the original dependencies.py
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_mongo_policy_store() -> MongoPolicyStore:
    """Returns the shared MongoDB-backed policy store instance."""
    return MongoPolicyStore()


@lru_cache(maxsize=1)
def get_mongo_chat_store() -> MongoChatStore:
    """Returns the shared MongoDB-backed chat store instance."""
    return MongoChatStore()


def get_policy_store() -> PolicyStore:
    """Returns the shared policy store instance for the API process.

    The API is backed by MongoDB so policy data survives process restarts.
    """
    return get_mongo_policy_store()


@lru_cache(maxsize=1)
def get_approval_manager() -> ApprovalManager:
    """Returns the shared approval manager bound to the shared store."""
    return ApprovalManager(get_policy_store())


@lru_cache(maxsize=1)
def get_policy_engine() -> PolicyEngine:
    """Returns the shared policy engine bound to the shared store."""
    return PolicyEngine(
        store=get_policy_store(),
        approval_manager=get_approval_manager(),
    )


# ---------------------------------------------------------------------------
# MCP + LLM layer — singletons initialised in startup()
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_llm_client() -> GeminiClient:
    """Returns the shared Gemini LLM client.

    Constructed synchronously here; the underlying aiohttp session is
    created lazily on the first API call so construction is safe outside
    an async context.
    """
    return GeminiClient()


@lru_cache(maxsize=1)
def get_mcp_manager() -> MCPManager:
    """Returns the shared MCPManager with transports registered.

    Transports are registered here (synchronous operation).
    Connections are established later in startup() via connect_all().
    """
    manager = MCPManager()
    manager.register(
        StdioTransport(
            name="local-crud",
            command=sys.executable,
            args=[str(_MCP_SERVER_PATH)],
        )
    )
    context7_key = os.getenv("CONTEXT7_API_KEY")
    if context7_key:
        manager.register(
            StreamableHTTPTransport(
                name="context7",
                url="https://mcp.context7.com/mcp",
                headers={"CONTEXT7_API_KEY": context7_key},
            )
        )
    else:
        logger.info("CONTEXT7_API_KEY not set — running with local-crud MCP only.")
    return manager


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    """Returns the shared ToolRegistry bound to the shared MCPManager."""
    return ToolRegistry(get_mcp_manager())


@lru_cache(maxsize=1)
def get_tool_loop() -> ToolLoop:
    """Returns the shared ToolLoop wiring LLM + registry + policy together."""
    return ToolLoop(
        llm=get_llm_client(),
        registry=get_tool_registry(),
        policy=get_policy_engine(),
    )


# ---------------------------------------------------------------------------
# Agent layer
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_agent_manager() -> AgentManager:
    """Returns the shared AgentManager singleton.

    One AgentManager lives for the lifetime of the process.  It holds a
    registry of active Agent instances, each with its own conversation history,
    all sharing the single ToolLoop returned by get_tool_loop().
    """
    return AgentManager(tool_loop=get_tool_loop, chat_store=get_mongo_chat_store())


# ---------------------------------------------------------------------------
# Lifespan helpers — called by app.py's @asynccontextmanager lifespan
# ---------------------------------------------------------------------------

async def startup() -> None:
    """Connects all MCP transports and warms up the tool registry.

    Must be awaited inside the lifespan startup block in app.py so that
    MCP servers are live before the first request arrives.
    """
    manager = get_mcp_manager()
    await manager.connect_all()

    # Initialize the Mongo-backed policy store eagerly so startup fails fast
    # if the database is unavailable or credentials are invalid.
    get_policy_store()
    get_mongo_chat_store()

    registry = get_tool_registry()
    await registry.discover()

    logger.info(
        "MCP startup complete — %d tools discovered across %d servers.",
        registry.count,
        len(manager.sessions()),
    )


async def shutdown() -> None:
    """Disconnects MCP transports and closes the LLM client.

    Must be awaited inside the lifespan shutdown block in app.py.
    """
    await get_mcp_manager().disconnect_all()
    if get_llm_client.cache_info().currsize:
        await get_llm_client().close()
    if get_mongo_policy_store.cache_info().currsize:
        get_mongo_policy_store().close()
    if get_mongo_chat_store.cache_info().currsize:
        get_mongo_chat_store().close()
    logger.info("MCP and LLM client shut down cleanly.")


