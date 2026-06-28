import asyncio
import os
import sys
import traceback
from contextlib import AsyncExitStack

from dotenv import load_dotenv

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()


async def connect_local_server(stack, server_path):
    print("➡ Connecting to ArmorIQ_Local_CRUD...")

    params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
    )

    read_stream, write_stream = await stack.enter_async_context(
        stdio_client(params)
    )

    session = await stack.enter_async_context(
        ClientSession(read_stream, write_stream)
    )

    await session.initialize()

    print("✅ ArmorIQ_Local_CRUD connected.\n")
    return session


async def connect_context7(stack):
    print("➡ Connecting to Context7...")

    api_key = os.getenv("CONTEXT7_API_KEY")

    if not api_key:
        raise ValueError("CONTEXT7_API_KEY not found in .env")

    read_stream, write_stream, _ = await stack.enter_async_context(
        streamablehttp_client(
            "https://mcp.context7.com/mcp",
            headers={
                "CONTEXT7_API_KEY": api_key
            },
        )
    )

    session = await stack.enter_async_context(
        ClientSession(read_stream, write_stream)
    )

    await session.initialize()

    print("✅ Context7 connected.\n")
    return session


async def discover_tools(name, session):
    print(f"\n🛠 {name}")

    response = await session.list_tools()

    print(f"Found {len(response.tools)} tools\n")

    for tool in response.tools:
        print(f"• {tool.name}")
        print(f"  {tool.description}\n")

    return len(response.tools)


async def main():

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    local_server_path = os.path.join(parent_dir, "server.py")

    active_sessions = {}

    async with AsyncExitStack() as stack:

        print("=" * 60)
        print("🚀 Booting MCP Ecosystem")
        print("=" * 60)

        # ---------------- Local Server ----------------

        try:
            active_sessions["ArmorIQ_Local_CRUD"] = await connect_local_server(
                stack,
                local_server_path,
            )
        except Exception:
            print("❌ Local server connection failed")
            traceback.print_exc()

        # ---------------- Context7 ----------------

        try:
            active_sessions["Context7"] = await connect_context7(stack)
        except Exception:
            print("❌ Context7 connection failed")
            traceback.print_exc()

        # ---------------- Tool Discovery ----------------

        print("\n" + "=" * 60)
        print("🔍 Discovering Tools")
        print("=" * 60)

        total = 0

        for name, session in active_sessions.items():
            try:
                total += await discover_tools(name, session)
            except Exception:
                print(f"❌ Failed to list tools for {name}")
                traceback.print_exc()

        print("\n" + "=" * 60)
        print(f"🎉 Total tools discovered: {total}")
        print("=" * 60)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(
            asyncio.WindowsProactorEventLoopPolicy()
        )

    asyncio.run(main())