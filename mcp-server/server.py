"""
Custom MCP Server — File Manager
Exposes 5 tools: read_file, write_file, list_directory, delete_file, search_files
Follows MCP spec: tool listing, schema, execution, error handling
Transport: stdio (plug-and-play with the agent)
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
    ListToolsResult,
)

# All file operations are sandboxed to this base directory
SANDBOX_DIR = Path(os.environ.get("SANDBOX_DIR", "./sandbox")).resolve()
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

app = Server("custom-file-mcp")


def resolve_safe_path(raw_path: str) -> Path:
    """
    Resolves a user-provided path and ensures it stays inside SANDBOX_DIR.
    Raises ValueError if the resolved path escapes the sandbox.
    """
    resolved = (SANDBOX_DIR / raw_path.lstrip("/")).resolve()
    if not str(resolved).startswith(str(SANDBOX_DIR)):
        raise ValueError(
            f"Path '{raw_path}' is outside the allowed sandbox directory."
        )
    return resolved


@app.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="read_file",
                description="Read the contents of a file inside the sandbox.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path to the file inside the sandbox (e.g. 'notes.txt')",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="write_file",
                description="Write or overwrite a file inside the sandbox.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path to the file inside the sandbox.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content to write into the file.",
                        },
                    },
                    "required": ["path", "content"],
                },
            ),
            Tool(
                name="list_directory",
                description="List files and subdirectories inside a sandbox directory.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path inside the sandbox. Use '.' for root.",
                            "default": ".",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="delete_file",
                description="Delete a file from the sandbox. This action is irreversible.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path to the file to delete.",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="search_files",
                description="Search for files by name or content pattern inside the sandbox.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Filename substring or text to search for inside file contents.",
                        },
                        "search_content": {
                            "type": "boolean",
                            "description": "If true, searches inside file contents too. Default is false (filename only).",
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]
    )


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        if name == "read_file":
            path = resolve_safe_path(arguments["path"])
            if not path.exists():
                raise FileNotFoundError(f"File not found: {arguments['path']}")
            content = path.read_text(encoding="utf-8")
            return CallToolResult(
                content=[TextContent(type="text", text=content)]
            )

        elif name == "write_file":
            path = resolve_safe_path(arguments["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding="utf-8")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"File written successfully: {arguments['path']}",
                    )
                ]
            )

        elif name == "list_directory":
            raw = arguments.get("path", ".")
            dir_path = resolve_safe_path(raw)
            if not dir_path.exists() or not dir_path.is_dir():
                raise NotADirectoryError(f"Directory not found: {raw}")
            entries = []
            for item in sorted(dir_path.iterdir()):
                kind = "dir" if item.is_dir() else "file"
                entries.append(f"[{kind}] {item.name}")
            result = "\n".join(entries) if entries else "(empty directory)"
            return CallToolResult(
                content=[TextContent(type="text", text=result)]
            )

        elif name == "delete_file":
            path = resolve_safe_path(arguments["path"])
            if not path.exists():
                raise FileNotFoundError(f"File not found: {arguments['path']}")
            path.unlink()
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Deleted: {arguments['path']}",
                    )
                ]
            )

        elif name == "search_files":
            query = arguments["query"].lower()
            search_content = arguments.get("search_content", False)
            matches = []
            for file in SANDBOX_DIR.rglob("*"):
                if not file.is_file():
                    continue
                rel = str(file.relative_to(SANDBOX_DIR))
                if query in file.name.lower():
                    matches.append(f"[name match] {rel}")
                elif search_content:
                    try:
                        text = file.read_text(encoding="utf-8", errors="ignore")
                        if query in text.lower():
                            matches.append(f"[content match] {rel}")
                    except Exception:
                        pass
            result = "\n".join(matches) if matches else "No files matched."
            return CallToolResult(
                content=[TextContent(type="text", text=result)]
            )

        else:
            raise ValueError(f"Unknown tool: {name}")

    except (FileNotFoundError, NotADirectoryError, ValueError) as e:
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
        )
    except Exception as e:
        return CallToolResult(
            isError=True,
            content=[
                TextContent(
                    type="text",
                    text=f"Unexpected error in tool '{name}': {str(e)}",
                )
            ],
        )


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
