import asyncio
import os

os.environ.pop("SSLKEYLOGFILE", None)

import shlex
from pathlib import Path

from bson.objectid import ObjectId
from dotenv import load_dotenv
from google import genai
from google.genai import types

from .db import MongoUnavailable, create_approval_request, get_approvals_collection, log_tool_action
from .mcp_infra.manager import McpClientManager
from .policy import PolicyEngine


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _get_gemini_api_key(api_key: str | None = None) -> str:
    resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_api_key:
        raise ValueError("GEMINI_API_KEY is missing. Add it to your .env file.")
    return resolved_api_key


def _mcp_result_data(mcp_output) -> dict:
    if isinstance(mcp_output, dict):
        return mcp_output
    if hasattr(mcp_output, "content"):
        return {"result": mcp_output.content}
    return {"result": str(mcp_output)}


def _configured_mcp_servers(env=os.environ) -> list[dict]:
    servers = []

    def add_server(prefix: str, default_id: str | None = None):
        server_id = env.get(f"{prefix}_ID", default_id)
        command = env.get(f"{prefix}_COMMAND")
        args = env.get(f"{prefix}_ARGS", "")
        sse_url = env.get(f"{prefix}_SSE_URL")
        url = env.get(f"{prefix}_URL")
        transport = env.get(f"{prefix}_TRANSPORT", "").lower()

        if not transport:
            if sse_url:
                transport = "sse"
            elif url:
                transport = "http"
            elif command:
                transport = "stdio"

        if not server_id or not transport:
            return

        if transport == "sse" and sse_url:
            servers.append({"id": server_id, "transport": "sse", "url": sse_url})
        elif transport in {"http", "streamable_http"} and url:
            servers.append({"id": server_id, "transport": "http", "url": url})
        elif transport == "stdio" and command:
            servers.append(
                {
                    "id": server_id,
                    "transport": "stdio",
                    "command": command,
                    "args": shlex.split(args),
                }
            )

    add_server("MCP_SERVER", "local")
    add_server("MCP_REMOTE_SERVER")

    index = 1
    while any(
        f"MCP_SERVER_{index}_{suffix}" in env
        for suffix in ("ID", "COMMAND", "ARGS", "URL", "SSE_URL", "TRANSPORT")
    ):
        add_server(f"MCP_SERVER_{index}", f"server-{index}")
        index += 1

    deduped = []
    seen = set()
    for server in servers:
        if server["id"] in seen:
            continue
        seen.add(server["id"])
        deduped.append(server)
    return deduped


class GuardedAgent:
    def __init__(self, mcp_manager: McpClientManager | None = None, api_key: str = None):
        """
        Initializes the Guarded Gemini Agent.
        Requires the `google-genai` package.
        """
        self.mcp_manager = mcp_manager or McpClientManager()
        self._started = False
        self.client = genai.Client(api_key=_get_gemini_api_key(api_key))
        self.conversations: dict[str, list[types.Content]] = {}

    async def start(self):
        if self._started:
            return

        await self.mcp_manager.__aenter__()
        for server in _configured_mcp_servers():
            if server["transport"] == "sse":
                await self.mcp_manager.register_sse_server(server["id"], server["url"])
            elif server["transport"] == "http":
                await self.mcp_manager.register_http_server(server["id"], server["url"])
            elif server["transport"] == "stdio":
                await self.mcp_manager.register_stdio_server(
                    server["id"],
                    server["command"],
                    server["args"],
                    env=os.environ.copy(),
                )

        self._started = True

    async def stop(self):
        if self._started:
            await self.mcp_manager.__aexit__(None, None, None)
            self._started = False

    async def run(self, message: str, conversation_id: str = "default") -> str:
        return await self.run_conversation_turn(conversation_id, message)

    async def list_tools(self) -> list[dict]:
        tools = []
        for server_id, registry in self.mcp_manager.tool_registry.items():
            for tool in registry:
                tools.append({
                    "server_id": server_id,
                    "name": f"{server_id}__{tool.name}",
                    "description": getattr(tool, "description", "") or "",
                    "inputSchema": getattr(tool, "inputSchema", None),
                })
        return tools

    def _format_mcp_to_gemini_tool(self, server_id: str, mcp_tool) -> types.FunctionDeclaration:
        """
        Converts an MCP JSON schema into Gemini's FunctionDeclaration format.
        Namespaces the tool as server_id__tool_name to prevent naming collisions.
        """
        return types.FunctionDeclaration(
            name=f"{server_id}__{mcp_tool.name}",
            description=mcp_tool.description,
            parameters=mcp_tool.inputSchema,
        )

    async def _wait_for_approval(
        self,
        conversation_id: str,
        server_id: str,
        tool_name: str,
        tool_args: dict,
    ) -> bool:
        try:
            approval_id = create_approval_request(conversation_id, server_id, tool_name, tool_args)
        except MongoUnavailable:
            return False
        if not approval_id:
            return False

        print(f"Agent paused. Awaiting human approval for ticket: {approval_id}")

        for _ in range(30):
            await asyncio.sleep(2)
            try:
                ticket = get_approvals_collection().find_one({"_id": ObjectId(approval_id)})
            except MongoUnavailable:
                return False
            if ticket and ticket.get("status") == "approved":
                return True
            if ticket and ticket.get("status") == "denied":
                return False

        return False

    async def run_conversation_turn(self, conversation_id: str, user_message: str) -> str:
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        history = self.conversations[conversation_id]
        history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)],
            )
        )

        gemini_functions = []
        for server_id, tools in self.mcp_manager.tool_registry.items():
            for tool in tools:
                gemini_functions.append(self._format_mcp_to_gemini_tool(server_id, tool))

        agent_tools = [types.Tool(function_declarations=gemini_functions)] if gemini_functions else []

        while True:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=history,
                config=types.GenerateContentConfig(
                    tools=agent_tools,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    temperature=0.1,
                ),
            )

            history.append(response.candidates[0].content)
            function_calls = response.function_calls

            if not function_calls:
                return response.text

            tool_responses = []
            for fn_call in function_calls:
                qualified_name = fn_call.name
                tool_args = dict(fn_call.args) if fn_call.args else {}

                if "__" not in qualified_name:
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=qualified_name,
                            response={"error": "Malformed tool signature: missing namespace delimiter."},
                        )
                    )
                    continue

                server_id, tool_name = qualified_name.split("__", 1)
                decision = await PolicyEngine.evaluate_tool(server_id, tool_name, tool_args)

                try:
                    await log_tool_action(
                        conversation_id,
                        server_id,
                        tool_name,
                        tool_args,
                        decision["action"],
                        decision.get("reason", ""),
                    )
                except MongoUnavailable:
                    pass

                if decision["action"] == "BLOCK":
                    result_data = {
                        "error": f"Security Exception: Action denied. Reason: {decision['reason']}"
                    }
                elif decision["action"] == "REQUIRE_APPROVAL":
                    approved = await self._wait_for_approval(
                        conversation_id, server_id, tool_name, tool_args
                    )
                    if approved:
                        mcp_output = await self.mcp_manager.call_tool_safe(qualified_name, tool_args)
                        result_data = _mcp_result_data(mcp_output)
                    else:
                        result_data = {
                            "error": "Security Exception: Action rejected by admin or timed out."
                        }
                else:
                    mcp_output = await self.mcp_manager.call_tool_safe(qualified_name, tool_args)
                    result_data = _mcp_result_data(mcp_output)

                tool_responses.append(
                    types.Part.from_function_response(
                        name=qualified_name,
                        response=result_data,
                    )
                )

            history.append(
                types.Content(
                    role="user",
                    parts=tool_responses,
                )
            )
