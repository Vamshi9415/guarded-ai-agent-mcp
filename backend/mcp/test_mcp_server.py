import asyncio
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession
import sys 
import os 

current_dir = os.path.dirname(os.path.abspath(__file__))
server_path = os.path.join(current_dir, "mcp_server.py")

async def test_mcp_Server():
    server_param = StdioServerParameters(
        command = sys.executable,
        args = [server_path],
        env = None
    )
    
    print("Starting MCP")
    
    async with stdio_client(server_param) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session :
            await session.initialize()
            print("initialization completed")
            
            tools = await session.list_tools()
            
            for tool in tools.tools :
                print(f"{tool.name}")
            print("\n")
            
            
            #testing tool execution 
            
            print(" Testing execution of list_records")
            
            result  = await session.call_tool("list_records", arguments = {})
            
            print(result)

if __name__ == "__main__" :
    asyncio.run(test_mcp_Server())
    
            
            
            
            
            