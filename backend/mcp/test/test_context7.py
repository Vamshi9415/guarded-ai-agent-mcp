import asyncio
import os

from dotenv import load_dotenv

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()

CONTEXT7_API_KEY = os.getenv("CONTEXT7_API_KEY")


async def main():
    headers = {
        "CONTEXT7_API_KEY": CONTEXT7_API_KEY
    }

    async with streamablehttp_client(
        "https://mcp.context7.com/mcp",
        headers=headers,
    ) as (read_stream, write_stream, _):

        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            print("✅ Connected to Context7")

            response = await session.list_tools()

            print(f"\nFound {len(response.tools)} tools:\n")

            for tool in response.tools:
                print(f"- {tool.name}")
                print(f"  {tool.description}\n")


if __name__ == "__main__":
    asyncio.run(main())