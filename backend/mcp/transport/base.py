from abc import ABC, abstractmethod 

from mcp.client.session import ClientSession 

class MCPTransport(ABC):
    "BASE INTERFACES FOR THE ALL MCP TRANSPORTS"
    
    def __init__(self, name : str):
        self.name = name
        self.session : ClientSession | None = None 
    
    @abstractmethod
    async def connect(self) -> ClientSession :
        pass 
    
    @abstractmethod 
    async def disconnect(self):
        pass 
    
    async def list_tools(self):
        return await self.session.list_tools()
    
    async def call_tool(self,tool_name : str, args : dict):
        return await self.session.call_tool(tool_name,args)