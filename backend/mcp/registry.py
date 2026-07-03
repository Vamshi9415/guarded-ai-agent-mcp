from __future__ import annotations

import logging
from typing import Any

from .manager import MCPManager
from .models import RegisteredTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, manager: MCPManager):
        self.manager = manager
        self._tools: dict[str, RegisteredTool] = {}
        self.failed_discovery: dict[str, str] = {}

    # ---------------------------
    # Discovery
    # ---------------------------

    async def discover(self) -> None:
        logger.info("Starting MCP tool discovery.")
        self._tools.clear()
        self.failed_discovery = {}

        sessions = self.manager.sessions()
        logger.debug("Connected sessions available for discovery: %s", list(sessions.keys()))

        for server_name, session in sessions.items():
            logger.info("Discovering tools from %s", server_name)

            try:
                response = await session.list_tools()
                logger.debug(
                    "Server '%s' returned %d tool(s).",
                    server_name,
                    len(response.tools),
                )
            except Exception as exc:
                logger.exception("Failed to discover tools from server '%s'", server_name)
                self.failed_discovery[server_name] = f"{type(exc).__name__}: {exc}"
                continue

            for tool in response.tools:
                logger.debug(
                    "Inspecting tool name=%s server=%s",
                    tool.name,
                    server_name,
                )

                if tool.name in self._tools:
                    logger.error(
                        "Duplicate tool detected: %s (server=%s)",
                        tool.name,
                        server_name,
                    )
                    raise ValueError(f"Duplicate tool detected: {tool.name}")

                self._tools[tool.name] = RegisteredTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema,
                    server_name=server_name,
                    session=session,
                )

                logger.debug(
                    "Registered tool name=%s server=%s",
                    tool.name,
                    server_name,
                )

        logger.info("Discovered %s total tool(s).", len(self._tools))

        if self.failed_discovery:
            logger.warning("Tool discovery failures: %s", self.failed_discovery)

        if not self._tools:
            logger.warning("Tool discovery completed, but no tools were registered.")

    # ---------------------------
    # Queries
    # ---------------------------

    def list(self) -> list[RegisteredTool]:
        logger.debug("Listing %d registered tool(s).", len(self._tools))
        return list(self._tools.values())

    def exists(self, tool_name: str) -> bool:
        exists = tool_name in self._tools
        logger.debug("Tool exists check: %s -> %s", tool_name, exists)
        return exists

    def get(self, tool_name: str) -> RegisteredTool:
        if tool_name not in self._tools:
            logger.error("Requested tool not found: %s", tool_name)
            raise KeyError(f"{tool_name} not found")

        logger.debug("Resolved tool '%s' from registry.", tool_name)
        return self._tools[tool_name]

    # ---------------------------
    # Execution
    # ---------------------------

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ):
        tool = self.get(tool_name)

        logger.info(
            "Executing tool=%s server=%s",
            tool.name,
            tool.server_name,
        )
        logger.debug(
            "Tool arguments for %s: %r",
            tool.name,
            arguments,
        )

        result = await tool.session.call_tool(
            tool.name,
            arguments,
        )

        logger.debug(
            "Execution finished for tool=%s server=%s",
            tool.name,
            tool.server_name,
        )

        return result

    # ---------------------------
    # Refresh
    # ---------------------------

    async def refresh(self) -> None:
        logger.info("Refreshing tool registry.")
        await self.discover()

    # ---------------------------
    # Statistics
    # ---------------------------

    @property
    def count(self) -> int:
        return len(self._tools)

    def grouped(self) -> dict[str, list[RegisteredTool]]:
        grouped: dict[str, list[RegisteredTool]] = {}

        for tool in self._tools.values():
            grouped.setdefault(tool.server_name, []).append(tool)

        logger.debug(
            "Grouped tools by server: %s",
            {k: len(v) for k, v in grouped.items()},
        )
        return grouped