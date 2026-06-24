import os
os.environ.pop("SSLKEYLOGFILE", None)
import shlex
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .mcp_infra.manager import McpClientManager
from .policy import PolicyEngine
from .db import log_tool_action


load_dotenv(Path(__file__).resolve().parents[1] / '.env')


def _get_gemini_api_key(api_key: str | None = None) -> str:
    resolved_api_key = api_key or os.getenv('GEMINI_API_KEY')
    if not resolved_api_key:
        raise ValueError('GEMINI_API_KEY is missing. Add it to your .env file.')
    return resolved_api_key


class GuardedAgent:
    def __init__(self, mcp_manager: McpClientManager | None = None, api_key: str = None):
        """
        Initializes the Guarded Gemini Agent.
        Requires the `google-genai` package.
        """
        self.mcp_manager = mcp_manager or McpClientManager()
        self._started = False
        
        # Initialize the official unified Google GenAI Client
        self.client = genai.Client(api_key=_get_gemini_api_key(api_key))
        
        # Simple chat memory tracking to maintain conversation structure
        self.conversations: dict[str, list[types.Content]] = {}

    async def start(self):
        if self._started:
            return

        await self.mcp_manager.__aenter__()
        server_id = os.getenv("MCP_SERVER_ID", "local")
        sse_url = os.getenv("MCP_SERVER_SSE_URL")
        command = os.getenv("MCP_SERVER_COMMAND")
        args = os.getenv("MCP_SERVER_ARGS")

        if sse_url:
            await self.mcp_manager.register_sse_server(server_id, sse_url)
        elif command:
            await self.mcp_manager.register_stdio_server(
                server_id,
                command,
                shlex.split(args or ""),
                env=os.environ.copy(),
            )

        self._started = True

    async def stop(self):
        if self._started:
            await self.mcp_manager.__aexit__(None, None, None)
            self._started = False

    async def run(self, message: str, conversation_id: str = "default") -> str:
        return await self.run_conversation_turn(conversation_id, message)

    async def list_tools(self) -> list[dict]:
        tools = []
        for server_id, registry in self.mcp_manager.tool_registry.items():
            for tool in registry:
                tools.append({
                    "server_id": server_id,
                    "name": f"{server_id}__{tool.name}",
                    "description": getattr(tool, "description", "") or "",
                    "inputSchema": getattr(tool, "inputSchema", None),
                })
        return tools
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
                model='gemini-2.5-flash-lite', # Fast, low-latency model optimized for tool orchestration
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
