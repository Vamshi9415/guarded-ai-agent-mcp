import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

class McpClientManager:
    def __init__(self):
        # Keeps all dynamic context managers alive across methods
        self._exit_stack = AsyncExitStack()
        # Maps server_id -> active initialized ClientSession
        self.sessions: dict[str, ClientSession] = {}
        # Maps server_id -> raw tools schema lists
        self.tool_registry: dict[str, list] = {} 

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Automatically shuts down all background processes and networks cleanly
        await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def register_stdio_server(self, server_id: str, command: str, args: list, env: dict = None):
        """Spawns a local MCP server as a subprocess and holds the connection open."""
        try:
            server_params = StdioServerParameters(command=command, args=args, env=env)
            
            # Enter the stdio client context and track it in the class-level stack
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
            
            # Enter the session context and track it
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            self.sessions[server_id] = session
              
            # Run Live Dynamic Discovery
            tools_response = await session.list_tools()
            self.tool_registry[server_id] = tools_response.tools
            
            print(f"Successfully connected and registered stdio server: {server_id}")
        except Exception as e:
            print(f"Failed to hook up stdio server {server_id}: {e}")

    async def register_sse_server(self, server_id: str, url: str):
        """Establishes a persistent streaming connection to a remote HTTP/SSE MCP server."""
        try:
            # Note the 3-tuple unpacking format required by the official client library
            read, write, _ = await self._exit_stack.enter_async_context(sse_client(url))
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            
            await session.initialize()
            self.sessions[server_id] = session
            
            tools_response = await session.list_tools()
            self.tool_registry[server_id] = tools_response.tools
            print(f"Successfully connected and registered SSE server: {server_id}")
        except Exception as e:
            print(f"Failed to hook up SSE server {server_id}: {e}")


    async def register_http_server(self, server_id: str, url: str):
        """Establishes a persistent streamable HTTP connection to a remote MCP server."""
        try:
            read, write, _ = await self._exit_stack.enter_async_context(
                streamablehttp_client(url)
            )
            session = await self._exit_stack.enter_async_context(ClientSession(read, write))

            await session.initialize()
            self.sessions[server_id] = session

            tools_response = await session.list_tools()
            self.tool_registry[server_id] = tools_response.tools
            print(f"Successfully connected and registered HTTP server: {server_id}")
        except Exception as e:
            print(f"Failed to hook up HTTP server {server_id}: {e}")

    async def call_tool_safe(self, qualified_name: str, args: dict):
        """Routes the structured request to the correct active sub-server."""
        if "__" not in qualified_name:
            return {"isError": True, "content": f"Invalid namespaced tool handle: {qualified_name}"}

        server_id, tool_name = qualified_name.split("__", 1)
        session = self.sessions.get(server_id)
        
        if not session:
            return {"isError": True, "content": f"Target server '{server_id}' is down or unregistered."}
            
        try:
            result = await session.call_tool(tool_name, arguments=args)
            return result
        except Exception as e:
            return {"isError": True, "content": f"MCP execution error inside '{server_id}': {str(e)}"}
