'''Custom MCP Server - File Manager
5 tools: read_file, write_file, list_directory, delete_file, search_files
FastMCP decorator style - auto schema, plug-and-play
Sandboxed paths only
'''

import os
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(name="custom-file-mcp")


SANDBOX_DIR = (
    Path(os.environ.get("SANDBOX_DIR", "./sandbox"))
    .resolve()
    .absolute()
)
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)


def _safe_path(raw: str) -> Path:
    """Resolve and validate a path stays inside sandbox."""
    p = (SANDBOX_DIR / raw.strip().lstrip("/\\")).resolve().absolute()
    if not str(p).startswith(str(SANDBOX_DIR)):
        raise ValueError("Path outside sandbox - blocked")
    return p


@mcp.tool()
def read_file(path: str) -> str:
    """Read the full contents of a file in the sandbox."""
    try:
        p = _safe_path(path)
        return p.read_text(encoding="utf-8")
    except ValueError as e:
        return f"Security error: {e}"
    except FileNotFoundError:
        return f"File not found: {path}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file in the sandbox. Overwrites if exists."""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"File written: {p.relative_to(SANDBOX_DIR)}"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List all files and folders inside a sandbox directory."""
    try:
        p = _safe_path(path)
        if not p.is_dir():
            return f"Not a directory: {path}"
        entries = []
        for item in p.iterdir():
            kind = "DIR " if item.is_dir() else "FILE"
            entries.append(f"{kind} {item.name}")
        return "\n".join(sorted(entries)) if entries else "(empty)"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def delete_file(path: str) -> str:
    """Delete a single file in the sandbox. Folders blocked."""
    try:
        p = _safe_path(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.is_dir():
            return "Cannot delete directories - use a file path only"
        p.unlink()
        return f"Deleted: {p.relative_to(SANDBOX_DIR)}"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def search_files(pattern: str) -> str:
    """Search for files in sandbox by filename pattern."""
    try:
        results = []
        for f in SANDBOX_DIR.rglob("**/*"):
            if f.is_file() and pattern.lower() in f.name.lower():
                results.append(str(f.relative_to(SANDBOX_DIR)))
        return "\n".join(results) if results else f"No files matched '{pattern}'"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
