import asyncio
import os
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client


async def main():
    import os

    IS_CLOUD = os.environ.get("ENVIRONMENT") == "production"

    servers = {
    "local-file-mcp": {
        "type": "stdio",                    # always stdio — your own server
        "command": "python",
        "args": ["mcp-server/server.py"],
        "env": {**os.environ, "SANDBOX_DIR": "./sandbox"},
    },
    "remote-context7": {
        "type": "http" if IS_CLOUD else "stdio",    # auto-switch
        "url": "https://mcp.context7.com/mcp",      # used when type=http
        "command": "npx",                            # used when type=stdio
        "args": ["-y", "@upstash/context7-mcp@latest"],
        "env": {**os.environ},
    },
}

    async with AsyncExitStack() as stack:
        sessions = {}

        for server_id, config in servers.items():
            print(f"Connecting to {server_id}...")
            try:
                if config["type"] == "stdio":
                    params = StdioServerParameters(
                        command=config["command"],
                        args=config["args"],
                        env=config.get("env"),
                    )
                    read, write = await stack.enter_async_context(
                        stdio_client(params)
                    )

                elif config["type"] == "sse":
                    read, write, _ = await stack.enter_async_context(   # 3-tuple
                        sse_client(config["url"])
                    )

                else:
                    print(f"Unknown transport type for {server_id}")
                    continue

                session = await stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                sessions[server_id] = session
                print(f"Connected: {server_id}")

            except Exception as e:
                print(f"Failed to connect to {server_id}: {e}")

        # Discover all tools from all connected servers
        print("\n--- Discovered Tools ---")
        for server_id, session in sessions.items():
            try:
                result = await session.list_tools()
                print(f"\n[{server_id}] {len(result.tools)} tools:")
                for tool in result.tools:
                    print(f"  - {tool.name}: {tool.description}")
            except Exception as e:
                print(f"Failed to list tools for {server_id}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
    