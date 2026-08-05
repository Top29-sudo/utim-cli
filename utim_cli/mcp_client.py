import os
import json
import asyncio
import threading
from typing import Dict, List, Any, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    HAS_MCP_LIB = True
except ImportError:
    HAS_MCP_LIB = False

# =========================================================================
# Pure-Python Stdio MCP Client Fallback (Zero C/Rust/pydantic-core dependency)
# =========================================================================
class PurePythonMCPTool:
    def __init__(self, name: str, description: str, inputSchema: dict):
        self.name = name
        self.description = description
        self.inputSchema = inputSchema

class PurePythonMCPContent:
    def __init__(self, text: str):
        self.text = text

class PurePythonMCPResult:
    def __init__(self, content: list, isError: bool = False):
        self.content = content
        self.isError = isError

class PurePythonMCPSession:
    """Pure-Python line-delimited JSON-RPC stdio client for MCP servers."""
    def __init__(self, command: str, args: list, env: dict):
        self.command = command
        self.args = args
        self.env = env
        self.proc = None
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    async def start(self):
        import sys
        import shutil
        current_dir = os.path.dirname(os.path.abspath(__file__))
        wrapper_path = os.path.join(current_dir, "mcp_clean_wrapper.py")
        resolved_command = shutil.which(self.command) or self.command

        cmd_list = [sys.executable, "-u", wrapper_path, resolved_command] + self.args
        self.proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env
        )

    async def _send_request(self, method: str, params: dict) -> dict:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("MCP process stdin not open")
        req_id = self._next_id()
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }) + "\n"
        self.proc.stdin.write(payload.encode("utf-8"))
        await self.proc.stdin.drain()

        while True:
            line = await self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server process output ended unexpectedly.")
            line_str = line.decode("utf-8", errors="ignore").strip()
            if not line_str:
                continue
            try:
                msg = json.loads(line_str)
                if msg.get("id") == req_id:
                    if "error" in msg:
                        err_msg = msg["error"].get("message", "MCP RPC Error")
                        raise RuntimeError(err_msg)
                    return msg.get("result", {})
            except json.JSONDecodeError:
                continue

    async def _send_notification(self, method: str, params: dict):
        if not self.proc or not self.proc.stdin:
            return
        payload = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }) + "\n"
        self.proc.stdin.write(payload.encode("utf-8"))
        await self.proc.stdin.drain()

    async def initialize(self):
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "utim", "version": "1.0"}
        })
        await self._send_notification("notifications/initialized", {})

    async def list_tools(self):
        res = await self._send_request("tools/list", {})
        raw_tools = res.get("tools", [])
        tools = []
        for t in raw_tools:
            tools.append(PurePythonMCPTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {})
            ))
        class ToolListResult:
            def __init__(self, t_list):
                self.tools = t_list
        return ToolListResult(tools)

    async def call_tool(self, name: str, arguments: dict):
        res = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        is_error = res.get("isError", False)
        raw_content = res.get("content", [])
        contents = []
        for c in raw_content:
            if isinstance(c, dict) and "text" in c:
                contents.append(PurePythonMCPContent(c["text"]))
            elif isinstance(c, str):
                contents.append(PurePythonMCPContent(c))
        if not contents:
            contents.append(PurePythonMCPContent(json.dumps(res)))
        return PurePythonMCPResult(contents, isError=is_error)

    async def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                await self.proc.wait()
            except Exception:
                pass


class MCPManager:
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self._exit_stacks = {}
        self._tool_to_server: Dict[str, str] = {}
        self._started = False
        self.cached_tools: List[Dict[str, Any]] = []
        self.server_tools: Dict[str, List[str]] = {}  # server_name -> list of tool names
        self._loop = None
        self._thread = None

    def start_loop(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run_coro(self, coro):
        self.start_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def start(self):
        if self._started:
            return
        
        from utim_cli.config import get_utim_dir
        config_path = os.path.abspath(os.path.join(get_utim_dir(), "mcp.json"))
        if not os.path.exists(config_path):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump({"mcpServers": {}}, f, indent=2)

        self.start_loop()
        self.run_coro(self._start_async())

    async def _start_async(self):
        from utim_cli.config import get_utim_dir
        config_path = os.path.abspath(os.path.join(get_utim_dir(), "mcp.json"))
        if not os.path.exists(config_path):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w") as f:
                json.dump({"mcpServers": {}}, f, indent=2)
            self._started = True
            return

        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            self._started = True
            return

        servers = config.get("mcpServers") or {}
        if not isinstance(servers, dict):
            servers = {}
        
        for name, srv_config in servers.items():
            command = srv_config.get("command")
            args = srv_config.get("args", [])
            env = srv_config.get("env", {})
            
            if not command:
                continue

            cleaned_args = []
            for arg in args:
                if isinstance(arg, str):
                    if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
                        arg = arg[1:-1]
                cleaned_args.append(arg)

            try:
                merged_env = os.environ.copy()
                merged_env.update(env)

                if HAS_MCP_LIB:
                    import sys
                    import shutil
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    wrapper_path = os.path.join(current_dir, "mcp_clean_wrapper.py")
                    resolved_command = shutil.which(command) or command
                    
                    server_params = StdioServerParameters(
                        command=sys.executable,
                        args=["-u", wrapper_path, resolved_command] + cleaned_args,
                        env=merged_env
                    )
                    
                    from contextlib import AsyncExitStack
                    stack = AsyncExitStack()
                    self._exit_stacks[name] = stack
                    
                    read, write = await stack.enter_async_context(stdio_client(server_params))
                    session = await stack.enter_async_context(ClientSession(read, write))
                    await asyncio.wait_for(session.initialize(), timeout=60.0)
                    self.sessions[name] = session
                else:
                    # Pure-Python stdio client fallback (Android Termux / minimal installs)
                    session = PurePythonMCPSession(command, cleaned_args, merged_env)
                    await session.start()
                    await asyncio.wait_for(session.initialize(), timeout=60.0)
                    self.sessions[name] = session
                
                # Retrieve tools from the server and cache them
                try:
                    res = await session.list_tools()
                    self.server_tools[name] = []
                    for t in res.tools:
                        full_name = f"{name}__{t.name}"
                        self._tool_to_server[full_name] = name
                        self.server_tools[name].append(t.name)
                        
                        self.cached_tools.append({
                            "type": "function",
                            "function": {
                                "name": full_name,
                                "description": f"[{name}] {t.description}",
                                "parameters": t.inputSchema
                            }
                        })
                except Exception as e:
                    print(f"Error fetching tools from MCP server {name}: {e}")
                    
            except Exception as e:
                print(f"Error starting MCP server {name}: {e}")
                
        self._started = True

    def get_tools(self) -> List[Dict[str, Any]]:
        """Synchronously returns the cached list of MCP tools."""
        return self.cached_tools

    def get_notification_context(self) -> str:
        """Returns the context notification string for connected MCP servers."""
        from utim_cli.config import config
        disabled = config.get("disabled_tools") or []
        if not isinstance(disabled, list):
            disabled = []
        notifications = []
        for server_name, tool_names in self.server_tools.items():
            enabled_tool_names = [t for t in tool_names if f"{server_name}__{t}" not in disabled]
            if enabled_tool_names:
                tools_str = ", ".join(enabled_tool_names)
                notifications.append(f"this mcp server {server_name} is connected and a new set of tools are available for u: {tools_str}")
        return "\n".join(notifications)

    def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Synchronously routes tool call execution to the background thread."""
        return self.run_coro(self._call_tool_async(server_name, tool_name, arguments))

    async def _call_tool_async(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        if server_name not in self.sessions:
            return f"Error: MCP server '{server_name}' not running."
            
        session = self.sessions[server_name]
        try:
            res = await session.call_tool(tool_name, arguments)
            if getattr(res, "isError", False):
                return f"Error from {server_name}: " + "\n".join(c.text for c in res.content)
            return "\n".join(c.text for c in res.content)
        except Exception as e:
            return f"Error calling {tool_name} on {server_name}: {str(e)}"

    def restart(self):
        """Synchronously restarts and reloads all MCP sessions."""
        self.run_coro(self._restart_async())

    async def _restart_async(self):
        for name, stack in list(self._exit_stacks.items()):
            try:
                await stack.aclose()
            except Exception:
                pass
        for name, session in list(self.sessions.items()):
            if hasattr(session, "close"):
                try:
                    await session.close()
                except Exception:
                    pass
        self.sessions.clear()
        self._exit_stacks.clear()
        self._tool_to_server.clear()
        self.cached_tools.clear()
        self.server_tools.clear()
        self._started = False
        await self._start_async()

mcp_manager = MCPManager()
