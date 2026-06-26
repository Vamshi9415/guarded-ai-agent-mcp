import asyncio
import os
import sys
from pathlib import Path
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent 

sys.path.insert(0,str(root_dir))

from dotenv import load_dotenv

from backend.agent.agent import Agent
from backend.agent.tool_loop import ToolLoop, AllowAllPolicy
from backend.llm.gemini import GeminiClient

# import your existing classes
from backend.mcp.manager import MCPManager
from backend.mcp.registry import ToolRegistry
from backend.mcp.transport.stdio_transport import StdioTransport
from backend.mcp.transport.streamble_http_transport import StreamableHTTPTransport

load_dotenv()


async def main():

    llm = GeminiClient()

    manager = MCPManager()

    manager.register(
        StdioTransport(
            name="local",
            command=sys.executable,
            args=[str(root_dir / "backend" / "mcp" / "server.py")],
        )
    )

    context7_api_key = os.getenv("CONTEXT7_API_KEY")
    manager.register(
        StreamableHTTPTransport(
            name="context7",
            url="https://mcp.context7.com/mcp",
            headers={"CONTEXT7_API_KEY": context7_api_key} if context7_api_key else {},
        )
    )

    await manager.connect_all()

    print("\n========== MCP SESSIONS ==========")
    for name, session in manager.sessions().items():
        print(name, "connected=" + str(session is not None))
    print("==================================")

    registry = ToolRegistry(manager)

    await registry.discover()
    print("\n========== REGISTRY ==========")
    print("Count:", registry.count)
    
    for tool in registry.list():
        print(tool.name)
        print(tool.description)
    
    print("==============================")

    loop = ToolLoop(
        llm=llm,
        registry=registry,
        policy=AllowAllPolicy(),
    )

    agent = Agent(loop)

    try:
        while True:

            prompt = input("\nYou: ")

            if prompt.lower() == "exit":
                break

            answer = await agent.chat(prompt)

            print("\nAgent:", answer)
    finally:
        await llm.close()
        await manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(main())

