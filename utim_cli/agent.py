import os
import json
import sys
import time
from .tools import get_tools
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.syntax import Syntax

# ─── Tool display metadata ────────────────────────────────────────────────────
# Color constants for consolidated 3-color palette
PURPLE = "#cba6f7"
BLUE = "#42bcf5"
YELLOW = "#f9e2af"

TOOL_META = {
    "read_file":      {"icon": "📄", "verb": "ReadFile",      "color": BLUE},
    "write_file":     {"icon": "✏️",  "verb": "WriteFile",     "color": YELLOW},
    "edit_file":      {"icon": "✂️",  "verb": "EditFile",      "color": YELLOW},
    "move_file":      {"icon": "📦",  "verb": "MoveFile",      "color": BLUE},
    "delete_file":    {"icon": "🗑️ ", "verb": "DeleteFile",    "color": PURPLE},
    "run_command":    {"icon": "⚡",  "verb": "RunCommand",    "color": YELLOW},
    "list_directory": {"icon": "📁",  "verb": "ReadFolder",    "color": PURPLE},
}

TIPS = [
    "Tip: Use /help to see all available commands and the help panel",
    "Tip: Save your current conversation with /resume save <tag>",
    "Tip: Clear conversation history with /clear",
    "Tip: Check your quota limits and credit usage with /usage",
    "Tip: Enable or disable individual tools with /tools",
    "Tip: Switch models with /model",
]

class ReActAgent:
    """A standalone agent that can reason and execute tools with streaming."""

    def __init__(self, name: str, model_id: str, system_prompt: str, console: Console = None):
        self.name = name
        self.model_id = model_id
        self.console = console or Console()
        self._tip_index = 0

        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENRouter_API_KEY")
        if not api_key:
            self.console.print("[dim]⚠  Warning: OPENROUTER_API_KEY is not set.[/dim]")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The legacy ReActAgent requires the optional OpenAI SDK. "
                "Install it with: pip install 'utim-cli[legacy-agent]'"
            ) from exc

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key or "sk-fake-key-for-init",
            default_headers={
                "HTTP-Referer": "https://utim.dev",
                "X-Title": "UTIM CLI Agent",
                "User-Agent": "UTIM-CLI/2.0 (+https://utim.dev)",
            },
        )
        self.messages = [{"role": "system", "content": system_prompt}]
        self.start_time = None

    def add_user_message(self, message: str):
        self.messages.append({"role": "user", "content": message})

    def get_elapsed_time(self):
        if self.start_time is None:
            return "0s"
        elapsed = int(time.time() - self.start_time)
        return f"{elapsed // 60}m {elapsed % 60}s" if elapsed >= 60 else f"{elapsed}s"

    def _next_tip(self):
        tip = TIPS[self._tip_index % len(TIPS)]
        self._tip_index += 1
        return tip

    def _render_tool_panel(self, func_name: str, args: dict, result: str):
        """Render a rich panel for a completed tool call."""
        meta = TOOL_META.get(func_name, {"icon": "●", "verb": func_name, "color": "white"})
        icon   = meta["icon"]
        verb   = meta["verb"]
        color  = meta["color"]

        # Header line
        header = Text()
        header.append("✓  ", style=f"bold {color}")
        header.append(verb, style=f"bold {color}")

        # Show the primary argument (filepath or command)
        primary_arg = (
            args.get("filepath")
            or args.get("command")
            or args.get("path")
            or args.get("src")
            or ""
        )
        if primary_arg:
            header.append(f"  {primary_arg}", style="white")

        # Body
        body = Text()

        if func_name == "write_file":
            body.append(result, style="dim")

        elif func_name == "edit_file":
            body.append(result, style="dim")

        elif func_name == "read_file":
            lines = result.split("\n")
            body.append(f"Read {len(lines)} lines", style="dim")

        elif func_name == "run_command":
            out = str(result).strip()
            if len(out) > 300:
                out = out[:300] + "\n[…truncated]"
            body.append(out, style="dim")

        elif func_name == "list_directory":
            items = [l for l in str(result).split("\n") if l.strip()]
            body.append(f"Listed {max(0, len(items)-1)} item(s).", style="dim")

        elif func_name == "move_file":
            body.append(result, style="dim")

        elif func_name == "delete_file":
            body.append(result, style="dim")

        else:
            out = str(result).strip()
            if len(out) > 300:
                out = out[:300] + "\n[…]"
            body.append(out, style="dim")

        content = header + "\n" + body

        self.console.print(Panel(
            content,
            border_style=color,
            expand=False,
        ))

    def _execute_tool_call(self, tool_call):
        """Execute a single tool call by name."""
        tool_name = tool_call["function"]["name"]
        
        # Clean corrupted tool name (e.g. from buggy OpenRouter proxy XML to tool-call translations)
        # E.g. 'read_file filepath=".utim/UTIM.md" />'
        arguments = {}
        raw_args = tool_call["function"].get("arguments", "{}")
        if raw_args:
            try:
                arguments = json.loads(raw_args)
                if not isinstance(arguments, dict):
                    arguments = {}
            except Exception:
                pass

        tool_name_clean = tool_name.strip("<> ")
        if tool_name_clean:
            parts = tool_name_clean.split(None, 1)
            actual_name = parts[0]
            if len(parts) > 1:
                attr_string = parts[1].rstrip("/> ")
                import re
                attrs = re.findall(r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', attr_string)
                for key, val1, val2, val3 in attrs:
                    val = val1 or val2 or val3 or ""
                    arguments[key] = val
            tool_name = actual_name

        # Map common alias tool names to actual UTIM CLI tool names
        _TOOL_NAME_ALIASES = {
            "shell": "run_command",
            "bash": "run_command",
            "cmd": "run_command",
            "execute_command": "run_command",
            "view_file": "read_file",
        }
        if tool_name in _TOOL_NAME_ALIASES:
            tool_name = _TOOL_NAME_ALIASES[tool_name]

        # Update the tool_call dict back with the cleaned values
        tool_call["function"]["name"] = tool_name
        tool_call["function"]["arguments"] = json.dumps(arguments)

        arguments = json.loads(tool_call["function"]["arguments"])

        # Show the tool is running
        meta = TOOL_META.get(tool_name, {"icon": "●", "verb": tool_name, "color": "white"})
        self.console.print(f"  {meta['icon']}  {meta['verb']} running...", style=f"dim {meta['color']}")

        if "__" in tool_name:
            server_name, actual_tool_name = tool_name.split("__", 1)
            try:
                from utim_cli.mcp_client import mcp_manager
                if server_name in mcp_manager.sessions:
                    self.console.print(f"  🔌  Calling MCP tool {server_name} ➔ {actual_tool_name}...", style="dim #cba6f7")
                    result = mcp_manager.call_tool(server_name, actual_tool_name, arguments)
                    
                    # Temporarily register metadata for render
                    TOOL_META[tool_name] = {"icon": "🔌", "verb": f"Calling {server_name} ➔ {actual_tool_name}", "color": "#cba6f7"}
                    self._render_tool_panel(tool_name, arguments, result)
                    return str(result)
            except Exception as e:
                return f"Error executing MCP tool {tool_name}: {str(e)}"

        utim_tools, tool_functions = get_tools()
        if tool_name not in tool_functions:
            # If not a standard tool, check MCP
            if hasattr(self, 'orchestrator') and self.orchestrator and tool_name in self.orchestrator.mcp_tool_names:
                return self.orchestrator._execute_mcp_tool(tool_name, arguments)
            return f"Error: Tool '{tool_name}' not found."
            
        try:
            result = tool_functions[tool_name](**arguments)
            self._render_tool_panel(tool_name, arguments, result)
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    def run(self, max_iterations: int = 500, show_tools: bool = True):
        """Run the agent loop with streaming."""
        self.start_time = time.time()

        for i in range(max_iterations):
            assistant_content = ""
            tool_calls = []
            current_tool_call = None

            utim_tools, tool_functions = get_tools()
            all_tools = utim_tools

            kwargs = {
                "model": self.model_id,
                "messages": self.messages,
                "stream": True,
            }
            if all_tools:
                kwargs["tools"] = all_tools

            # Call the LLM with streaming
            stream = self.client.chat.completions.create(**kwargs)

            # Collect streaming chunks
            for chunk in stream:
                delta = chunk.choices[0].delta

                if delta.content:
                    assistant_content += delta.content

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_index = tc.index if tc.index is not None else 0
                        if current_tool_call is None or tc_index != current_tool_call.get("index"):
                            # Flush the previous buffered tool call (check index, not id)
                            if current_tool_call is not None:
                                tool_calls.append(current_tool_call)
                            current_tool_call = {
                                "index": tc_index,
                                "id": tc.id or "",
                                "type": tc.type or "function",
                                "function": {
                                    "name": tc.function.name if tc.function else "",
                                    "arguments": tc.function.arguments if tc.function else "",
                                },
                            }
                        else:
                            # Same tool call — accumulate the argument chunks
                            if tc.id and not current_tool_call["id"]:
                                current_tool_call["id"] = tc.id
                            if tc.function and tc.function.arguments:
                                current_tool_call["function"]["arguments"] += tc.function.arguments

            # Flush the last buffered tool call
            if current_tool_call is not None:
                tool_calls.append(current_tool_call)

            # Parse XML-style tool calls if present in the text content
            from .client_utils import parse_xml_tool_calls
            parsed_content, parsed_tool_calls = parse_xml_tool_calls(assistant_content)
            if parsed_tool_calls:
                assistant_content = parsed_content or ""
                tool_calls.extend(parsed_tool_calls)

            # Print any text content generated by the assistant
            if assistant_content.strip():
                self.console.print()
                self.console.print(Markdown(assistant_content))
                # Only add a trailing newline if there are no tool calls following
                if not tool_calls:
                    self.console.print()

            # If no tool calls, we are done
            if not tool_calls:
                break

            # Save the assistant message with tool_calls
            self.messages.append({
                "role": "assistant",
                "content": assistant_content if assistant_content else None,
                "tool_calls": tool_calls,
            })

            # Execute each tool call
            for tc in tool_calls:
                result = self._execute_tool_call(tc)

                # Add tool result to messages
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                })
        else:
            self.console.print(f"\n[bold yellow]⚠ Agent paused after reaching maximum iterations ({max_iterations}).[/bold yellow]")
            self.console.print("[dim]You can type 'continue' to resume the task.[/dim]\n")

        elapsed = self.get_elapsed_time()
        tip = self._next_tip()
        self.console.print(Rule(f"[dim]⚙  {elapsed}  •  {tip}[/dim]"))

    def list_tools(self):
        """Display all available tools in a formatted table."""
        self.console.print()
        self.console.print(Rule("[bold accent]🔧 Available Tools[/bold accent]"))
        self.console.print()

        headers = ["Tool", "Description"]
        all_tools = []
        utim_tools, _ = get_tools()
        for tool_def in utim_tools:
            fn = tool_def["function"]
            all_tools.append((fn["name"], fn["description"], "standard"))

        try:
            from utim_cli.mcp_client import mcp_manager
            mcp_tools = mcp_manager.get_tools()
            for t in mcp_tools:
                fn = t["function"]
                all_tools.append((fn["name"], fn["description"], "mcp"))
        except Exception:
            pass

        if not all_tools:
            return

        # Load disabled tools config
        from utim_cli.config import config
        disabled = config.get("disabled_tools") or []
        if not isinstance(disabled, list):
            disabled = []

        col_widths = [max(len(t[0]) for t in all_tools) + 2, 60]
        
        # Header
        header_str = f"  {headers[0].ljust(col_widths[0])}  {headers[1]}"
        self.console.print(f"[bold accent]{header_str}[/bold accent]")
        self.console.print(Rule(style="dim"))
        
        for name, desc, t_type in all_tools:
            is_disabled = name in disabled
            status_tag = " [red][Disabled][/red]" if is_disabled else ""
            desc_str = f"{status_tag} [dim]{desc}[/dim]" if is_disabled else f"[dim]{desc}[/dim]"
            
            if t_type == "mcp":
                tool_str = f"  🔌  {name.ljust(col_widths[0] - 4)}  {desc_str}"
                self.console.print(f"[#cba6f7]{tool_str}[/#cba6f7]")
            else:
                meta = TOOL_META.get(name, {"icon": "●", "color": "white"})
                # Dim the icon and name color if disabled
                color = "dim" if is_disabled else meta['color']
                tool_str = f"  {meta['icon']}  {name.ljust(col_widths[0] - 4)}  {desc_str}"
                self.console.print(f"[{color}]{tool_str}[/{color}]")

        self.console.print()
