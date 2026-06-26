import sys

from contextlib import AsyncExitStack

from mcp.client.session import ClientSession 

from mcp.client.stdio import stdio_client, StdioServerParameters 

from .base import MCPTransport

class StdioTransport(MCPTransport):
    
    def __init__(self, name,command, args ):
        super().__init__(name)
        
        self.command = command 
        self.args = args 
        self.stack = AsyncExitStack()
    
    async def connect(self):
        params = StdioServerParameters(
            command = self.command,
            args = self.args 
        )
        
        read, write = await self.stack.enter_async_context(
            stdio_client(params)
        )
        
        self.session = await self.stack.enter_async_context(
            ClientSession(read,write)
        )
        
        await self.session.initialize()
        
        return self.session 
    
    async def disconnect(self):
        return self.stack.aclose()