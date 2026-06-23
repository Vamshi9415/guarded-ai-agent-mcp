# Custom File Manager MCP Server

A plug-and-play MCP server that exposes **5 sandboxed file management tools** to the AI agent. It follows the MCP spec: tool listing, JSON schema, execution, and structured error handling.

---

## Tools exposed

| Tool | Description |
|---|---|
| `read_file` | Read contents of a file inside the sandbox |
| `write_file` | Write or overwrite a file inside the sandbox |
| `list_directory` | List files and folders in a sandbox directory |
| `delete_file` | Delete a file (great for testing the block rule!) |
| `search_files` | Search by filename or content pattern |

All file operations are **sandboxed** — paths outside `./sandbox/` are rejected with a structured error.

---

## Setup

```bash
cd mcp-server
pip install -r requirements.txt
```

---

## Run the server

```bash
python server.py
```

The server uses **stdio transport** — the agent spawns it as a subprocess automatically.

---

## Connect to the agent

Add this to your agent's MCP server config:

```json
{
  "mcpServers": {
    "custom-file-mcp": {
      "command": "python",
      "args": ["mcp-server/server.py"],
      "env": {
        "SANDBOX_DIR": "./sandbox"
      }
    }
  }
}
```

No agent-side code changes are needed. The agent will auto-discover all 5 tools at startup.

---

## Sandbox safety

- All file paths are resolved and validated against `SANDBOX_DIR`.
- Any path traversal attempt (e.g. `../../etc/passwd`) is rejected with a clear error.
- `SANDBOX_DIR` defaults to `./sandbox` but can be overridden via env variable.

---

## Policy rules to try in the dashboard

| Rule | Type | Target tool |
|---|---|---|
| Block file deletion | Block Tool | `delete_file` |
| Require approval for writes | Human Approval | `write_file` |
| Enforce sandbox paths | Input Validation | `file_*` |
