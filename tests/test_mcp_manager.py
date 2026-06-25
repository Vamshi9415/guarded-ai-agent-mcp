from types import SimpleNamespace

import pytest

from backend.mcp_infra.manager import McpClientManager


@pytest.mark.asyncio
async def test_call_tool_safe_rejects_malformed_name():
    manager = McpClientManager()

    result = await manager.call_tool_safe("read_file", {"path": "a.txt"})

    assert result["isError"] is True
    assert "Invalid namespaced tool" in result["content"]


@pytest.mark.asyncio
async def test_call_tool_safe_reports_missing_session():
    manager = McpClientManager()

    result = await manager.call_tool_safe("local__read_file", {"path": "a.txt"})

    assert result["isError"] is True
    assert "down or unregistered" in result["content"]


@pytest.mark.asyncio
async def test_call_tool_safe_routes_to_correct_session():
    class Session:
        def __init__(self):
            self.calls = []

        async def call_tool(self, tool_name, arguments):
            self.calls.append((tool_name, arguments))
            return SimpleNamespace(content="ok")

    session = Session()
    manager = McpClientManager()
    manager.sessions["local"] = session

    result = await manager.call_tool_safe("local__read_file", {"path": "a.txt"})

    assert result.content == "ok"
    assert session.calls == [("read_file", {"path": "a.txt"})]


@pytest.mark.asyncio
async def test_call_tool_safe_wraps_session_errors():
    class FailingSession:
        async def call_tool(self, tool_name, arguments):
            raise RuntimeError("server crashed")

    manager = McpClientManager()
    manager.sessions["local"] = FailingSession()

    result = await manager.call_tool_safe("local__read_file", {})

    assert result["isError"] is True
    assert "server crashed" in result["content"]
