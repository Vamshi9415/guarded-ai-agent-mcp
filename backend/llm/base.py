from __future__ import annotations 

from abc import ABC, abstractmethod 

from dataclasses import dataclass, field
from typing import Any, Literal 

import uuid
Role = Literal["system","user","assistant","tool"]

class LLMError(Exception):
    """ just an error class for when llm provider call fails"""

@dataclass
class ToolCall :
    id :str
    name : str 
    args : dict[str,Any]
    
    @staticmethod
    def new_id() ->str :
        return uuid.uuid4().hex[:12]
    

class BaseLLMCLient(ABC):
    """ basic endpoint to generate the content"""
    




