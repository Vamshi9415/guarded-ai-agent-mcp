from types import SimpleNamespace

import pytest

from backend import agent as agent_module


class FakePart:
    @staticmethod
    def from_text(text):
        return {"text": text}

    @staticmethod
    def from_function_response(name, response):
        return {"function_response": {"name": name, "response": response}}


class FakeContent:
    def __init__(self, role, parts):
        self.role = role
        self.parts = parts


class FakeFunctionDeclaration:
    def __init__(self, name, description, parameters):
        self.name = name
        self.description = description
        self.parameters = parameters


class FakeTool:
    def __init__(self, function_declarations):
        self.function_declarations = function_declarations


class FakeGenerateContentConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeAutomaticFunctionCallingConfig:
    def __init__(self, disable):
        self.disable = disable


class FakeTypes:
    Part = FakePart
    Content = FakeContent
    FunctionDeclaration = FakeFunctionDeclaration
    Tool = FakeTool
    GenerateContentConfig = FakeGenerateContentConfig
    AutomaticFunctionCallingConfig = FakeAutomaticFunctionCallingConfig


class FakeResponse:
    def __init__(self, *, text="", function_calls=None, content=None):
        self.text = text
        self.function_calls = function_calls or []
        self.candidates = [SimpleNamespace(content=content or {"model": text})]


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake Gemini responses left")
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


class FakeMcpManager:
    def __init__(self):
        self.tool_registry = {
            "local": [
                SimpleNamespace(
                    name="read_file",
                    description="Read a file",
                    inputSchema={"type": "object"},
                )
            ]
        }
        self.calls = []
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True

    async def call_tool_safe(self, qualified_name, args):
        self.calls.append((qualified_name, args))
        return SimpleNamespace(content=[{"type": "text", "text": "tool output"}])


@pytest.fixture
def fake_types(monkeypatch):
    monkeypatch.setattr(agent_module, "types", FakeTypes)


@pytest.fixture
def fake_policy_and_log(monkeypatch):
    decisions = []
    logs = []

    async def evaluate_tool(server_id, tool_name, tool_args):
        if decisions:
            return decisions.pop(0)
        return {"action": "ALLOW", "reason": "ok"}

    async def log_tool_action(*args):
        logs.append(args)
        return "log-id"

    monkeypatch.setattr(agent_module.PolicyEngine, "evaluate_tool", evaluate_tool)
    monkeypatch.setattr(agent_module, "log_tool_action", log_tool_action)
    return decisions, logs



def last_tool_response(guarded, conversation_id):
    for item in reversed(guarded.conversations[conversation_id]):
        if getattr(item, "role", None) == "user" and item.parts:
            part = item.parts[0]
            if "function_response" in part:
                return part["function_response"]["response"]
    raise AssertionError("No tool response found in conversation history")

def make_agent(monkeypatch, responses):
    client = FakeClient(responses)
    monkeypatch.setattr(agent_module.genai, "Client", lambda api_key: client)
    manager = FakeMcpManager()
    guarded = agent_module.GuardedAgent(mcp_manager=manager, api_key="test-key")
    return guarded, manager, client


@pytest.mark.asyncio
async def test_list_tools_uses_live_registry(monkeypatch):
    guarded, _, _ = make_agent(monkeypatch, [])

    tools = await guarded.list_tools()

    assert tools == [{
        "server_id": "local",
        "name": "local__read_file",
        "description": "Read a file",
        "inputSchema": {"type": "object"},
    }]


def test_format_mcp_tool_namespaces_tool(monkeypatch, fake_types):
    guarded, _, _ = make_agent(monkeypatch, [])
    tool = SimpleNamespace(name="search", description="Search", inputSchema={"type": "object"})

    declaration = guarded._format_mcp_to_gemini_tool("remote", tool)

    assert declaration.name == "remote__search"
    assert declaration.description == "Search"
    assert declaration.parameters == {"type": "object"}


@pytest.mark.asyncio
async def test_agent_executes_allowed_tool_and_feeds_result_back(monkeypatch, fake_types, fake_policy_and_log):
    _, logs = fake_policy_and_log
    responses = [
        FakeResponse(function_calls=[SimpleNamespace(name="local__read_file", args={"path": "a.txt"})]),
        FakeResponse(text="final answer"),
    ]
    guarded, manager, client = make_agent(monkeypatch, responses)

    result = await guarded.run_conversation_turn("c1", "read a file")

    assert result == "final answer"
    assert manager.calls == [("local__read_file", {"path": "a.txt"})]
    assert logs[0][1:5] == ("local", "read_file", {"path": "a.txt"}, "ALLOW")
    assert len(client.models.calls) == 2
    assert last_tool_response(guarded, "c1") == {
        "result": [{"type": "text", "text": "tool output"}]
    }


@pytest.mark.asyncio
async def test_agent_blocks_tool_without_executing(monkeypatch, fake_types, fake_policy_and_log):
    decisions, logs = fake_policy_and_log
    decisions.append({"action": "BLOCK", "reason": "delete forbidden"})
    responses = [
        FakeResponse(function_calls=[SimpleNamespace(name="local__delete_file", args={"path": "a.txt"})]),
        FakeResponse(text="blocked final"),
    ]
    guarded, manager, _ = make_agent(monkeypatch, responses)

    result = await guarded.run_conversation_turn("c2", "delete a file")

    assert result == "blocked final"
    assert manager.calls == []
    assert logs[0][4] == "BLOCK"
    response = last_tool_response(guarded, "c2")
    assert "Action denied" in response["error"]


@pytest.mark.asyncio
async def test_agent_rejects_malformed_tool_name(monkeypatch, fake_types, fake_policy_and_log):
    responses = [
        FakeResponse(function_calls=[SimpleNamespace(name="delete_file", args={})]),
        FakeResponse(text="done"),
    ]
    guarded, manager, _ = make_agent(monkeypatch, responses)

    result = await guarded.run_conversation_turn("c3", "call malformed")

    assert result == "done"
    assert manager.calls == []
    response = last_tool_response(guarded, "c3")
    assert "Malformed tool signature" in response["error"]


@pytest.mark.asyncio
async def test_agent_approval_timeout_does_not_execute_tool(monkeypatch, fake_types, fake_policy_and_log):
    decisions, _ = fake_policy_and_log
    decisions.append({"action": "REQUIRE_APPROVAL", "reason": "ask admin"})
    responses = [
        FakeResponse(function_calls=[SimpleNamespace(name="local__write_file", args={"path": "a.txt"})]),
        FakeResponse(text="approval handled"),
    ]
    guarded, manager, _ = make_agent(monkeypatch, responses)
    monkeypatch.setattr(guarded, "_wait_for_approval", lambda *args: _async_bool(False))

    result = await guarded.run_conversation_turn("c4", "write file")

    assert result == "approval handled"
    assert manager.calls == []
    response = last_tool_response(guarded, "c4")
    assert "rejected" in response["error"]


@pytest.mark.asyncio
async def test_agent_executes_tool_after_approval(monkeypatch, fake_types, fake_policy_and_log):
    decisions, _ = fake_policy_and_log
    decisions.append({"action": "REQUIRE_APPROVAL", "reason": "ask admin"})
    responses = [
        FakeResponse(function_calls=[SimpleNamespace(name="local__write_file", args={"path": "a.txt"})]),
        FakeResponse(text="approved final"),
    ]
    guarded, manager, _ = make_agent(monkeypatch, responses)
    monkeypatch.setattr(guarded, "_wait_for_approval", lambda *args: _async_bool(True))

    result = await guarded.run_conversation_turn("c5", "write file")

    assert result == "approved final"
    assert manager.calls == [("local__write_file", {"path": "a.txt"})]


@pytest.mark.asyncio
async def test_start_registers_stdio_server_from_environment(monkeypatch):
    class LifecycleManager(FakeMcpManager):
        def __init__(self):
            super().__init__()
            self.registered = None

        async def register_stdio_server(self, server_id, command, args, env=None):
            self.registered = (server_id, command, args, env)

        async def register_http_server(self, server_id, url):
            raise AssertionError("Unexpected HTTP server registration")

    monkeypatch.setenv("MCP_SERVER_ID", "files")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "python")
    monkeypatch.setenv("MCP_SERVER_ARGS", "mcp-server/server.py --flag")
    monkeypatch.delenv("MCP_SERVER_SSE_URL", raising=False)
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    monkeypatch.delenv("MCP_SERVER_TRANSPORT", raising=False)
    monkeypatch.delenv("MCP_REMOTE_SERVER_ID", raising=False)
    monkeypatch.delenv("MCP_REMOTE_SERVER_URL", raising=False)
    monkeypatch.delenv("MCP_REMOTE_SERVER_SSE_URL", raising=False)
    monkeypatch.delenv("MCP_REMOTE_SERVER_TRANSPORT", raising=False)
    guarded, _, _ = make_agent(monkeypatch, [])
    manager = LifecycleManager()
    guarded.mcp_manager = manager

    await guarded.start()
    await guarded.stop()

    assert manager.entered is True
    assert manager.exited is True
    assert manager.registered[0:3] == ("files", "python", ["mcp-server/server.py", "--flag"])


@pytest.mark.asyncio
async def test_start_registers_local_and_remote_mcp_servers(monkeypatch):
    class LifecycleManager(FakeMcpManager):
        def __init__(self):
            super().__init__()
            self.stdio_servers = []
            self.http_servers = []

        async def register_stdio_server(self, server_id, command, args, env=None):
            self.stdio_servers.append((server_id, command, args, env))

        async def register_http_server(self, server_id, url):
            self.http_servers.append((server_id, url))

    monkeypatch.setenv("MCP_SERVER_ID", "local-file-mcp")
    monkeypatch.setenv("MCP_SERVER_COMMAND", "python")
    monkeypatch.setenv("MCP_SERVER_ARGS", "mcp-server/server.py")
    monkeypatch.delenv("MCP_SERVER_SSE_URL", raising=False)
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    monkeypatch.delenv("MCP_SERVER_TRANSPORT", raising=False)
    monkeypatch.setenv("MCP_REMOTE_SERVER_ID", "remote-context7")
    monkeypatch.setenv("MCP_REMOTE_SERVER_TRANSPORT", "http")
    monkeypatch.setenv("MCP_REMOTE_SERVER_URL", "https://mcp.context7.com/mcp")
    monkeypatch.delenv("MCP_REMOTE_SERVER_SSE_URL", raising=False)
    guarded, _, _ = make_agent(monkeypatch, [])
    manager = LifecycleManager()
    guarded.mcp_manager = manager

    await guarded.start()
    await guarded.stop()

    assert manager.stdio_servers[0][0:3] == ("local-file-mcp", "python", ["mcp-server/server.py"])
    assert manager.http_servers == [("remote-context7", "https://mcp.context7.com/mcp")]


async def _async_bool(value):
    return value

