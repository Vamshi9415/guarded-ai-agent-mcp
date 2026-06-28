import asyncio
import os
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

from backend.mcp.manager import MCPManager
from backend.mcp.transport.stdio_transport import StdioTransport
from backend.mcp.transport.streamble_http_transport import (
    StreamableHTTPTransport,
)

load_dotenv()


async def main():

    manager = MCPManager()

    manager.register(
        StdioTransport(
            name="local",
            command=sys.executable,
            args=[str(CURRENT_DIR.parent / "server.py")],
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