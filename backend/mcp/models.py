from dataclasses import dataclass 
from typing import Any

from mcp.client.session import ClientSession 

@dataclass 
class RegisteredTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    session: ClientSession