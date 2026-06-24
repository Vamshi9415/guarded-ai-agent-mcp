# ex.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(
        command="python",
        args=["mcp-server/server.py"],
        env={"SANDBOX_DIR": "./sandbox"},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()

            for tool in result.tools:
                print(f"{tool.name}: {tool.description}")

asyncio.run(main())