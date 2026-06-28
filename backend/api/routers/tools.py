"""Tool discovery routes for the FastAPI admin backend."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_tool_registry
from backend.api.schemas import ToolResponse, to_tool_response
from backend.mcp.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("", response_model=list[ToolResponse])
async def list_tools(registry: ToolRegistry = Depends(get_tool_registry)) -> list[ToolResponse]:
    """Returns the currently discovered MCP tools."""
    return [to_tool_response(tool) for tool in registry.list()]