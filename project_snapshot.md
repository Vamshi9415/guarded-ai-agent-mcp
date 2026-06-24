# Project Snapshot
- 📁 **./**
  - 📄 **client.py**
    ```py
    import asyncio
    import os
    from contextlib import AsyncExitStack
    
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.sse import sse_client
    
    
    async def main():
        import os
    
        IS_CLOUD = os.environ.get("ENVIRONMENT") == "production"
    
        servers = {
        "local-file-mcp": {
            "type": "stdio",                    # always stdio — your own server
            "command": "python",
            "args": ["mcp-server/server.py"],
            "env": {**os.environ, "SANDBOX_DIR": "./sandbox"},
        },
        "remote-context7": {
            "type": "http" if IS_CLOUD else "stdio",    # auto-switch
            "url": "https://mcp.context7.com/mcp",      # used when type=http
            "command": "npx",                            # used when type=stdio
            "args": ["-y", "@upstash/context7-mcp@latest"],
            "env": {**os.environ},
        },
    }
    
        async with AsyncExitStack() as stack:
            sessions = {}
    
            for server_id, config in servers.items():
                print(f"Connecting to {server_id}...")
                try:
                    if config["type"] == "stdio":
                        params = StdioServerParameters(
                            command=config["command"],
                            args=config["args"],
                            env=config.get("env"),
                        )
                        read, write = await stack.enter_async_context(
                            stdio_client(params)
                        )
    
                    elif config["type"] == "sse":
                        read, write, _ = await stack.enter_async_context(   # 3-tuple
                            sse_client(config["url"])
                        )
    
                    else:
                        print(f"Unknown transport type for {server_id}")
                        continue
    
                    session = await stack.enter_async_context(
                        ClientSession(read, write)
                    )
                    await session.initialize()
                    sessions[server_id] = session
                    print(f"Connected: {server_id}")
    
                except Exception as e:
                    print(f"Failed to connect to {server_id}: {e}")
    
            # Discover all tools from all connected servers
            print("\n--- Discovered Tools ---")
            for server_id, session in sessions.items():
                try:
                    result = await session.list_tools()
                    print(f"\n[{server_id}] {len(result.tools)} tools:")
                    for tool in result.tools:
                        print(f"  - {tool.name}: {tool.description}")
                except Exception as e:
                    print(f"Failed to list tools for {server_id}: {e}")
    
    
    if __name__ == "__main__":
        asyncio.run(main())
    ```
  - 📄 **ex.py**
    ```py
    # ex.py
    import asyncio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    async def main():
        params = StdioServerParameters(
            command="python",
            args=["mcp-server/server.py"],
            env={"SANDBOX_DIR": "./sandbox"},
        )
    
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
    
                for tool in result.tools:
                    print(f"{tool.name}: {tool.description}")
    
    asyncio.run(main())
    ```
  - 📄 **snapshot.py**
    ```py
    import os
    
    EXCLUDE = {'data','agent-test-output','venv311', '__pycache__', '.git', 'node_modules', '.pytest_cache','.env'}
    EXCLUDE_EXTENSIONS = {'.ps1','.pyc', '.pyo', '.pyd', '.db', '.sqlite', '.env'}
    
    def build_markdown(root_dir, output_file='project_snapshot.md'):
        lines = ['# Project Snapshot\n']
    
        # Avoid including the generated snapshot file inside itself.
        output_path = os.path.abspath(output_file)
    
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Skip excluded folders
            dirnames[:] = [d for d in sorted(dirnames) if d not in EXCLUDE]
            filenames = sorted(filenames)
    
            rel = os.path.relpath(dirpath, root_dir)
            depth = 0 if rel == '.' else rel.count(os.sep) + 1
            indent = '  ' * depth
            folder_name = os.path.basename(dirpath) if rel != '.' else os.path.basename(root_dir)
    
            lines.append(f'{indent}- 📁 **{folder_name}/**\n')
    
            for filename in filenames:
                if any(filename.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
                    continue
    
                filepath = os.path.join(dirpath, filename)
                if os.path.abspath(filepath) == output_path:
                    continue
                file_indent = '  ' * (depth + 1)
                rel_path = os.path.relpath(filepath, root_dir)
    
                lines.append(f'{file_indent}- 📄 **{filename}**\n')
    
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().strip()
    
                    if content:
                        ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
                        lang = ext if ext not in ('', 'md', 'txt', 'example') else ''
                        lines.append(f'{file_indent}  ```{lang}\n')
                        for line in content.splitlines():
                            lines.append(f'{file_indent}  {line}\n')
                        lines.append(f'{file_indent}  ```\n')
                    else:
                        lines.append(f'{file_indent}  *(empty)*\n')
    
                except Exception as e:
                    lines.append(f'{file_indent}  *(could not read: {e})*\n')
    
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    
        print(f'Done → {output_file}')
    
    if __name__ == '__main__':
        build_markdown('.')
    ```
  - 📁 **backend/**
    - 📄 **__init__.py**
      *(empty)*
    - 📄 **agent.py**
      ```py
      import os
      from google import genai
      from google.genai import types
      
      from mcp_infrastructure.manager import McpClientManager
      from policy import PolicyEngine
      from db import log_tool_action
      
      class GuardedAgent:
          def __init__(self, mcp_manager: McpClientManager, api_key: str = None):
              """
              Initializes the Guarded Gemini Agent.
              Requires the `google-genai` package.
              """
              self.mcp_manager = mcp_manager
              
              # Initialize the official unified Google GenAI Client
              self.client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))
              
              # Simple chat memory tracking to maintain conversation structure
              self.conversations: dict[str, list[types.Content]] = {}
      
          def _format_mcp_to_gemini_tool(self, server_id: str, mcp_tool) -> types.FunctionDeclaration:
              """
              Converts an MCP JSON schema into Gemini's FunctionDeclaration format.
              Namespaces the tool as server_id__tool_name to prevent naming collisions.
              """
              return types.FunctionDeclaration(
                  name=f"{server_id}__{mcp_tool.name}",
                  description=mcp_tool.description,
                  # Pass the MCP JSON Schema parameters directly into Gemini's schema field
                  parameters=mcp_tool.inputSchema 
              )
      
          async def run_conversation_turn(self, conversation_id: str, user_message: str) -> str:
              # 1. Load or initialize conversation history for this session
              if conversation_id not in self.conversations:
                  self.conversations[conversation_id] = []
              
              history = self.conversations[conversation_id]
              
              # Append the new incoming user instruction
              history.append(
                  types.Content(
                      role="user",
                      parts=[types.Part.from_text(text=user_message)]
                  )
              )
      
              # 2. Gather fresh tool schemas dynamically from the active MCP connection manager
              gemini_functions = []
              for server_id, tools in self.mcp_manager.tool_registry.items():
                  for tool in tools:
                      gemini_functions.append(self._format_mcp_to_gemini_tool(server_id, tool))
      
              # Wrap discovered schemas into Gemini's global Tool collection format
              agent_tools = [types.Tool(function_declarations=gemini_functions)] if gemini_functions else []
      
              while True:
                  # 3. Request generation from the model
                  response = self.client.models.generate_content(
                      model='gemini-2.5-flash', # Fast, low-latency model optimized for tool orchestration
                      contents=history,
                      config=types.GenerateContentConfig(
                          tools=agent_tools,
                          # ─── CRITICAL SECURITY STEP ───
                          # Completely stops the SDK from trying to automatically execute your python code
                          automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                          temperature=0.1
                      )
                  )
      
                  # Append the model's structural response block directly to our state tracking
                  history.append(response.candidates[0].content)
      
                  # 4. Check if the model emitted an intent to use tools
                  function_calls = response.function_calls
                  
                  # Case A: If no tools were called, the turn is done. Return the final answer.
                  if not function_calls:
                      return response.text
      
                  # Case B: Handle Tool Use Interception manually
                  tool_responses = []
                  
                  for fn_call in function_calls:
                      qualified_name = fn_call.name
                      tool_args = dict(fn_call.args) if fn_call.args else {}
                      
                      if "__" not in qualified_name:
                           tool_responses.append(
                               types.Part.from_function_response(
                                   name=qualified_name,
                                   response={"error": "Malformed tool signature: Missing namespace delimiter."}
                               )
                           )
                           continue
      
                      server_id, tool_name = qualified_name.split("__", 1)
      
                      # ─── THE SEAM: PROGRAMMATIC SECURITY EVALUATION ───
                      decision = await PolicyEngine.evaluate_tool(server_id, tool_name, tool_args)
                      
                      # Permanently audit log the attempt and decision parameters to MongoDB Atlas
                      await log_tool_action(
                          conversation_id, 
                          server_id, 
                          tool_name, 
                          tool_args, 
                          decision["action"], 
                          decision.get("reason", "")
                      )
      
                      if decision["action"] == "BLOCK":
                          # Generate a clean system error message shape
                          result_data = {"error": f"Security Exception: Action Denied. Reason: {decision['reason']}"}
                      
                      elif decision["action"] == "REQUIRE_APPROVAL":
                          # Handled via your FastAPI sync wait-gates
                          result_data = {"status": "Suspended: Awaiting real-time supervisor verification."}
                      
                      else:
                          # ALLOWED: Securely route execution to your McpClientManager context stacks
                          mcp_output = await self.mcp_manager.call_tool_safe(qualified_name, tool_args)
                          
                          # Convert MCP result objects or generic errors to a serializable data structure
                          if hasattr(mcp_output, 'content'):
                              result_data = {"result": mcp_output.content}
                          else:
                              result_data = {"result": str(mcp_output)}
      
                      # Enforce structure back to Gemini function response standards
                      tool_responses.append(
                          types.Part.from_function_response(
                              name=qualified_name,
                              response=result_data
                          )
                      )
      
                  # 5. Inject the intercepted responses back into the history stream.
                  # Gemini strictly mandates that tool execution outputs are delivered by the "user" role.
                  history.append(
                      types.Content(
                          role="user",
                          parts=tool_responses
                      )
                  )
                  
                  # The while loop repeats! Gemini processes the `tool_responses` data array we injected,
                  # and will either determine it needs another tool or output its final text answer.
      ```
    - 📄 **db.py**
      *(empty)*
    - 📄 **main.py**
      *(empty)*
    - 📄 **policy.py**
      *(empty)*
    - 📁 **mcp_infra/**
      - 📄 **__init__.py**
        *(empty)*
      - 📄 **manager.py**
        ```py
        import asyncio
        from contextlib import AsyncExitStack
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.sse import sse_client
        
        class McpClientManager:
            def __init__(self):
                # Keeps all dynamic context managers alive across methods
                self._exit_stack = AsyncExitStack()
                # Maps server_id -> active initialized ClientSession
                self.sessions: dict[str, ClientSession] = {}
                # Maps server_id -> raw tools schema lists
                self.tool_registry: dict[str, list] = {} 
        
            async def __aenter__(self):
                return self
        
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                # Automatically shuts down all background processes and networks cleanly
                await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)
        
            async def register_stdio_server(self, server_id: str, command: str, args: list, env: dict = None):
                """Spawns a local MCP server as a subprocess and holds the connection open."""
                try:
                    server_params = StdioServerParameters(command=command, args=args, env=env)
                    
                    # Enter the stdio client context and track it in the class-level stack
                    read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
                    
                    # Enter the session context and track it
                    session = await self._exit_stack.enter_async_context(ClientSession(read, write))
                    
                    await session.initialize()
                    self.sessions[server_id] = session
                      
                    # Run Live Dynamic Discovery
                    tools_response = await session.list_tools()
                    self.tool_registry[server_id] = tools_response.tools
                    
                    print(f"🚀 Successfully connected and registered stdio server: {server_id}")
                except Exception as e:
                    print(f"❌ Failed to hook up stdio server {server_id}: {e}")
        
            async def register_sse_server(self, server_id: str, url: str):
                """Establishes a persistent streaming connection to a remote HTTP/SSE MCP server."""
                try:
                    # Note the 3-tuple unpacking format required by the official client library
                    read, write, _ = await self._exit_stack.enter_async_context(sse_client(url))
                    session = await self._exit_stack.enter_async_context(ClientSession(read, write))
                    
                    await session.initialize()
                    self.sessions[server_id] = session
                    
                    tools_response = await session.list_tools()
                    self.tool_registry[server_id] = tools_response.tools
                    print(f"🌐 Successfully connected and registered SSE server: {server_id}")
                except Exception as e:
                    print(f"❌ Failed to hook up SSE server {server_id}: {e}")
        
            async def call_tool_safe(self, qualified_name: str, args: dict):
                """Routes the structured request to the correct active sub-server."""
                if "__" not in qualified_name:
                    return {"isError": True, "content": f"Invalid namespaced tool handle: {qualified_name}"}
        
                server_id, tool_name = qualified_name.split("__", 1)
                session = self.sessions.get(server_id)
                
                if not session:
                    return {"isError": True, "content": f"Target server '{server_id}' is down or unregistered."}
                    
                try:
                    result = await session.call_tool(tool_name, arguments=args)
                    return result
                except Exception as e:
                    return {"isError": True, "content": f"MCP execution error inside '{server_id}': {str(e)}"}
        ```
  - 📁 **mcp-server/**
    - 📄 **README.md**
      ```
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
      ```
    - 📄 **requirements.txt**
      ```
      mcp>=1.0.0
      ```
    - 📄 **server.py**
      ```py
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
      ```
    - 📁 **sandbox/**
      - 📄 **.gitkeep**
        *(empty)*
  - 📁 **sandbox/**
