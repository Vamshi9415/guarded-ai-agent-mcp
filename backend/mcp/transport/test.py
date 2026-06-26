import asyncio
import os
import sys

from dotenv import load_dotenv

from ..manager import MCPManager
from mcp.transport.stdio_transport import StdioTransport
from mcp.transport.streamable_http_transport import (
    StreamableHTTPTransport,
)

load_dotenv()


async def main():

    manager = MCPManager()

    manager.register(
        StdioTransport(
            name="local",
            command=sys.executable,
            args=["server.py"],
        )
    )

    manager.register(
        StreamableHTTPTransport(
            name="context7",
            url="https://mcp.context7.com/mcp",
            headers={
                "CONTEXT7_API_KEY": os.getenv(
                    "CONTEXT7_API_KEY"
                )
            },
        )
    )

    await manager.connect_all()

    for name, session in manager.sessions().items():

        print(f"\n{name}")

        tools = await session.list_tools()

        for tool in tools.tools:
            print(tool.name)

    await manager.disconnect_all()


asyncio.run(main())