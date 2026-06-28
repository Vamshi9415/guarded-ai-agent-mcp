import asyncio
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
import os
import sys 


current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
local_server_path = os.path.join(parent_dir, "server.py")

async def test_mcp_server():
    # 1. Define how to launch your custom server
    # Ensure "server.py" matches the name of the file you created earlier
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path], 
        env=None
    )

    print("🔄 Starting MCP Client and connecting to server...")
    
    # 2. Connect to the server via stdio transport
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            
            # 3. Initialize the protocol handshake
            await session.initialize()
            print("✅ Successfully initialized connection!\n")
            
            # 4. Test Tool Discovery (Crucial for your assignment)
            print("🔍 Fetching available tools from the server...")
            tools_response = await session.list_tools()
            
            for tool in tools_response.tools:
                print(f"  - {tool.name}")
            print("\n")

            # 5. Test Tool Execution 
            print("⚡ Testing execution of 'list_records'...")
            result = await session.call_tool("list_records", arguments={})
            
            # The MCP spec returns content as a list of text/image objects
            for content in result.content:
                print(f"Result:\n{content.text}")

if __name__ == "__main__":
    asyncio.run(test_mcp_server())