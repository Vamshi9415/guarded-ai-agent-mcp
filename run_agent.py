# run_agent.py  (place at the project root, next to backend/)
"""
Minimal manual entry point for the guarded agent. Wires MCP -> LLM ->
Policy -> Agent and drops into a REPL. Not container.py - just enough
to actually run agent.py from a terminal right now.
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from backend.mcp.manager import MCPManager
from backend.mcp.registry import ToolRegistry
from backend.mcp.transport.stdio_transport import StdioTransport
from backend.mcp.transport.streamble_http_transport import StreamableHTTPTransport
from backend.llm.gemini import GeminiClient
from backend.policy.store import InMemoryPolicyStore
from backend.policy.engine import PolicyEngine
from backend.agent.tool_loop import ToolLoop
from backend.agent.agent import Agent

SERVER_PATH = Path(__file__).parent / "backend" / "mcp" / "server.py"


async def build_manager() -> MCPManager:
    manager = MCPManager()

    manager.register(
        StdioTransport(name="local_crud", command=sys.executable, args=[str(SERVER_PATH)])
    )

    context7_key = os.getenv("CONTEXT7_API_KEY")
    if context7_key:
        manager.register(
            StreamableHTTPTransport(
                name="context7",
                url="https://mcp.context7.com/mcp",
                headers={"CONTEXT7_API_KEY": context7_key},
            )
        )
    else:
        print("CONTEXT7_API_KEY not set - running with local_crud only.")

    # Note: connect_all() has no per-transport error handling today - if
    # any registered server fails to connect, this raises and nothing
    # comes up at all. That's the "what happens when an MCP server
    # crashes" edge case, just encountered at startup instead of mid-
    # conversation - worth a try/except per-transport inside
    # MCPManager.connect_all() itself eventually, out of scope here.
    await manager.connect_all()
    return manager


async def main() -> None:
    manager = await build_manager()

    registry = ToolRegistry(manager)
    await registry.discover()
    print(f"Discovered {registry.count} tools across {len(manager.sessions())} server(s).")

    llm = GeminiClient()  # reads GEMINI_API_KEY from the environment
    store = InMemoryPolicyStore()
    
    rules = await store.list_rules()
    print(f"Loaded {len(rules)} policy rule(s)")
    policy = PolicyEngine(store)
    # ^ swap for AllowAllPolicy() (already in backend/agent/tool_loop.py)
    #   if you want to sanity-check the loop with guardrails out of the way.
    tool_loop = ToolLoop(llm, registry, policy)
    agent = Agent(tool_loop)

    print(f"Conversation: {agent.conversation_id}")
    print("Type 'exit' to quit, 'reset' to clear history.\n")

    try:
        while True:
            user_input = input("you> ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                break
            if user_input.lower() == "reset":
                agent.reset()
                print("(history cleared)")
                continue

            reply = await agent.chat(user_input)
            print(f"agent> {reply}\n")
    finally:
        await manager.disconnect_all()
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())