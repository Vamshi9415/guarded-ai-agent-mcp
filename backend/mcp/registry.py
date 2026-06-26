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

    # ---------------------------
    # Discovery
    # ---------------------------

    async def discover(self):

        self._tools.clear()

        sessions = self.manager.sessions()

        for server_name, session in sessions.items():

            logger.info("Discovering tools from %s", server_name)

            response = await session.list_tools()

            for tool in response.tools:

                if tool.name in self._tools:
                    raise ValueError(
                        f"Duplicate tool detected: {tool.name}"
                    )

                self._tools[tool.name] = RegisteredTool(
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.inputSchema,
                    server_name=server_name,
                    session=session,
                )

        logger.info("Discovered %s tools", len(self._tools))

    # ---------------------------
    # Queries
    # ---------------------------

    def list(self):

        return list(self._tools.values())

    def exists(self, tool_name: str):

        return tool_name in self._tools

    def get(self, tool_name: str):

        if tool_name not in self._tools:
            raise KeyError(f"{tool_name} not found")

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

        result = await tool.session.call_tool(
            tool.name,
            arguments,
        )

        return result

    # ---------------------------
    # Refresh
    # ---------------------------

    async def refresh(self):

        await self.discover()

    # ---------------------------
    # Statistics
    # ---------------------------

    @property
    def count(self):

        return len(self._tools)

    def grouped(self):

        grouped = {}

        for tool in self._tools.values():

            grouped.setdefault(
                tool.server_name,
                [],
            ).append(tool)

        return grouped