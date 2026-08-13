"""
SubAgent Manager — Nested Parallel Task Execution for UTIM CLI
==============================================================

Architecture
------------
Supports UNLIMITED nesting depth with configurable max_depth guard.

  Main Agent  (depth 0)
     │
     ├─ calls invoke_subagents(tasks=[...])
     │
     └─► SubAgentManager (depth 0)
              │
              ├─ SubAgent A  (depth 1)  ──► own model, tools, MCP, memory
              │      │
              │      └─► SubAgent A1  (depth 2) ─► own model, tools, MCP, memory
              │
              ├─ SubAgent B  (depth 1)  ──► own model, tools, MCP, memory
              └─ SubAgent C  (depth 1)  ──► own model, tools, MCP, memory

Each subagent has its own:
  - context_window  (isolated message history, no bleed from parent)
  - system_prompt   (fully custom per-agent, not inherited from parent)
  - model           (any UTIM-supported model, can differ from parent)
  - tools           (allowlist/denylist — restrict or expand tool access)
  - permissions     (read-only, write-blocked, shell-blocked, etc.)
  - mcp_servers     (list of MCP server names to connect; empty = parent's)
  - memory          (optional ChromaDB collection name for persistent RAG)
  - max_depth       (configurable ceiling, default MAX_NEST_DEPTH = 4)

Design rules:
  - Each subagent has an ISOLATED console (no interleaving)
  - Nesting depth tracked via _subagent_depth on each Orchestrator session
  - MAX_NEST_DEPTH = 4 hard ceiling (protects against runaway recursion)
  - Parent cancellation propagated to all child subagents recursively
  - Results returned in ORDER of input tasks array
  - Timeout per subagent configurable (default 300s)
  - Permissions enforce tool filtering — blocked tools return error strings
"""

from __future__ import annotations

import io
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_NEST_DEPTH = 4   # Hard ceiling on recursive subagent spawning
MAX_PARALLEL   = 8   # Max concurrent subagents at any single depth level


# ── Permission profiles ────────────────────────────────────────────────────────

#: Tool sets blocked under each named permission profile.
PERMISSION_PROFILES: Dict[str, Set[str]] = {
    # Full access — all tools available (default)
    "full": set(),

    # Read-only — may not write files, run commands, or delete
    "read_only": {
        "write_file", "apply_patch", "delete_file", "rename_file",
        "run_command", "run_script",
    },

    # No shell — may not execute any shell commands
    "no_shell": {"run_command", "run_script"},

    # No write — may not modify files but can run read-only commands
    "no_write": {
        "write_file", "apply_patch", "delete_file", "rename_file",
    },

    # Isolated — only memory and analysis tools; no filesystem or shell access
    "isolated": {
        "write_file", "apply_patch", "delete_file", "rename_file",
        "run_command", "run_script", "read_file", "list_directory",
        "search_files", "search_code",
    },
}


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class SubAgentTask:
    """
    Specification for a single nested subagent run.

    Fields
    ------
    task_id         — Unique identifier  e.g. "research-1", "write-tests"
    role            — Human label        e.g. "Researcher", "Test Writer"
    system_prompt   — Full system prompt for this subagent (not inherited)
    user_prompt     — The actual task instruction
    model_id        — Model to use (defaults to parent model if "")
    max_iterations  — Max LLM loops (default 20)
    timeout_seconds — Wall-clock timeout before cancellation (default 300)

    # Nested subagent capabilities (new in v2.3.0):
    allowed_tools   — If non-empty, ONLY these tool names are available
    blocked_tools   — Tool names to block (on top of permission profile)
    permission      — Named permission profile: "full" | "read_only" |
                      "no_shell" | "no_write" | "isolated"
    mcp_servers     — List of MCP server names to load for this subagent.
                      Empty list = inherit parent's active MCP servers.
    memory_collection — ChromaDB collection name for this subagent's
                        persistent memory (empty = no persistent memory)
    max_depth       — How many additional nesting levels this subagent may
                      spawn (0 = leaf node, cannot spawn further).
                      Capped by the global MAX_NEST_DEPTH.
    context_limit   — Optional max tokens for this subagent's context window.
                      Passed as max_context_tokens to the Orchestrator.
    """
    task_id:            str
    role:               str
    system_prompt:      str
    user_prompt:        str
    model_id:           str         = ""
    max_iterations:     int         = 20
    timeout_seconds:    int         = 300

    # Per-agent capabilities
    allowed_tools:      List[str]   = field(default_factory=list)
    blocked_tools:      List[str]   = field(default_factory=list)
    permission:         str         = "full"
    mcp_servers:        List[str]   = field(default_factory=list)
    memory_collection:  str         = ""
    max_depth:          int         = MAX_NEST_DEPTH
    context_limit:      int         = 0   # 0 = use model default


@dataclass
class SubAgentResult:
    """Result returned by a completed subagent."""
    task_id:    str
    role:       str
    success:    bool
    output:     str       # Final assistant response
    error:      str       = ""
    iterations: int       = 0
    elapsed_s:  float     = 0.0
    depth:      int       = 0   # depth at which this subagent ran


# ── Silent console ────────────────────────────────────────────────────────────

def _make_silent_console() -> Console:
    """
    Returns a Rich Console that writes to a StringIO buffer.
    Subagents use this so their internal tool-call output does not
    interleave with the main terminal display.
    """
    return Console(file=io.StringIO(), highlight=False, markup=True)


# ── Tool filtering helper ──────────────────────────────────────────────────────

def _build_tool_filter(
    task: SubAgentTask,
    all_tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Apply the subagent's permission profile, blocked_tools, and allowed_tools
    to produce the final tool list that will be visible to this subagent.

    Priority:
      1. Start with all available tools
      2. Remove tools blocked by the permission profile
      3. Remove explicitly blocked_tools
      4. If allowed_tools is non-empty, keep only those (allowlist)
    """
    # Step 1 — permission profile
    profile_blocked: Set[str] = PERMISSION_PROFILES.get(task.permission, set())

    # Step 2 — explicit user-specified block list
    extra_blocked: Set[str] = set(task.blocked_tools)

    combined_blocked = profile_blocked | extra_blocked

    filtered = [
        t for t in all_tools
        if t.get("function", {}).get("name") not in combined_blocked
    ]

    # Step 3 — allowlist (restrict to only named tools)
    if task.allowed_tools:
        allowed_set = set(task.allowed_tools)
        filtered = [
            t for t in filtered
            if t.get("function", {}).get("name") in allowed_set
        ]

    return filtered


# ── MCP server selection helper ────────────────────────────────────────────────

def _build_mcp_tools(task: SubAgentTask) -> List[Dict[str, Any]]:
    """
    Load MCP tools for this subagent.

    If task.mcp_servers is non-empty, only connect to those named servers.
    If empty, inherit the parent process's already-active MCP connections.
    """
    try:
        from utim_cli.mcp_client import mcp_manager
        if task.mcp_servers:
            # Selective MCP — only requested servers
            tools = []
            for tool in mcp_manager.get_tools():
                server_name = tool.get("_mcp_server", "")
                if server_name in task.mcp_servers:
                    tools.append(tool)
            return tools
        else:
            # Inherit parent's full MCP tool set
            return mcp_manager.get_tools()
    except Exception:
        return []


# ── Memory context injection helper ───────────────────────────────────────────

def _get_memory_context(memory_collection: str, user_prompt: str) -> str:
    """
    Query the subagent's dedicated ChromaDB memory collection for relevant
    context to prepend into its system prompt.

    Returns an empty string if memory_collection is empty or unavailable.
    """
    if not memory_collection:
        return ""
    try:
        from utim_cli.vector_memory import VectorMemory
        vm = VectorMemory(collection_name=memory_collection)
        results = vm.query(user_prompt, n_results=5)
        if not results:
            return ""
        lines = [f"\n\n### Persistent Memory ({memory_collection}) ###"]
        for r in results:
            doc = r.get("document", "")
            if doc:
                lines.append(f"- {doc[:500]}")
        return "\n".join(lines)
    except Exception:
        return ""


# ── SubAgent worker ───────────────────────────────────────────────────────────

def _run_subagent(
    task:           SubAgentTask,
    parent_model:   str,
    cancel_event:   threading.Event,
    current_depth:  int,
    status_lock:    threading.Lock,
    parent_console: Console,
) -> SubAgentResult:
    """
    Runs one subagent to completion inside a ThreadPoolExecutor worker.

    - Uses a silent console so output doesn't bleed into the main terminal.
    - Each subagent gets its own Orchestrator with isolated context, model,
      tools, permissions, MCP server selection, and optional memory.
    - Nested subagents are allowed up to min(task.max_depth, MAX_NEST_DEPTH).
    - Updates status on the parent console (thread-safe) when done.
    """
    t_start  = time.time()
    model_id = task.model_id or parent_model
    this_depth = current_depth + 1

    # Per-subagent cancel event (propagated from parent)
    sub_cancel = threading.Event()

    def _watch_parent():
        while not cancel_event.is_set() and not sub_cancel.is_set():
            time.sleep(0.3)
        if cancel_event.is_set():
            sub_cancel.set()

    watcher = threading.Thread(target=_watch_parent, daemon=True)
    watcher.start()

    silent = _make_silent_console()
    result_holder: Dict[str, Any] = {}

    try:
        from utim_cli.orchestrator import Orchestrator
        from utim_cli.tools import get_tools

        session = Orchestrator(console=silent)
        session.model_id     = model_id
        session.cancel_event = sub_cancel

        # ── Depth control ─────────────────────────────────────────────────
        # Allow further spawning only if task.max_depth permits
        effective_max_depth = min(task.max_depth, MAX_NEST_DEPTH)
        session._subagent_depth     = this_depth
        session._subagent_max_depth = effective_max_depth

        # ── Context window ────────────────────────────────────────────────
        if task.context_limit > 0:
            session._context_limit = task.context_limit

        # ── Memory context injection ──────────────────────────────────────
        memory_context = _get_memory_context(task.memory_collection, task.user_prompt)

        # ── System prompt (isolated — never inherited from parent) ────────
        full_system_prompt = task.system_prompt
        if memory_context:
            full_system_prompt = full_system_prompt + memory_context

        session.messages = [
            {"role": "system", "content": full_system_prompt},
        ]

        # ── Tool filtering ────────────────────────────────────────────────
        utim_tools, _ = get_tools()
        mcp_tools      = _build_mcp_tools(task)
        raw_tools      = utim_tools + mcp_tools
        filtered_tools = _build_tool_filter(task, raw_tools)

        # Inject invoke_subagents tool only if this agent is allowed to nest
        # (i.e., current depth < effective_max_depth)
        _invoke_subagents_schema = {
            "type": "function",
            "function": {
                "name": "invoke_subagents",
                "description": (
                    "Spawn one or more nested subagents to run tasks concurrently. "
                    "Each subagent has its own model, tools, permissions, MCP servers, "
                    "system prompt, and optional memory. Results are returned when all complete."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "description": "Array of subagent task definitions.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "task_id":           {"type": "string"},
                                    "role":              {"type": "string"},
                                    "system_prompt":     {"type": "string"},
                                    "user_prompt":       {"type": "string"},
                                    "model_id":          {"type": "string"},
                                    "max_iterations":    {"type": "integer"},
                                    "timeout_seconds":   {"type": "integer"},
                                    "allowed_tools":     {"type": "array", "items": {"type": "string"}},
                                    "blocked_tools":     {"type": "array", "items": {"type": "string"}},
                                    "permission":        {"type": "string", "enum": ["full", "read_only", "no_shell", "no_write", "isolated"]},
                                    "mcp_servers":       {"type": "array", "items": {"type": "string"}},
                                    "memory_collection": {"type": "string"},
                                    "max_depth":         {"type": "integer"},
                                    "context_limit":     {"type": "integer"},
                                },
                                "required": ["task_id", "role", "system_prompt", "user_prompt"],
                            }
                        }
                    },
                    "required": ["tasks"],
                },
            }
        }

        if this_depth < effective_max_depth:
            # Remove any existing invoke_subagents entry to avoid duplicates
            filtered_tools = [
                t for t in filtered_tools
                if t.get("function", {}).get("name") != "invoke_subagents"
            ]
            filtered_tools.append(_invoke_subagents_schema)

        # Store filtered tool override for the orchestrator to use
        session._subagent_tool_override = filtered_tools

        # ── Memory store on completion ────────────────────────────────────
        def _store_memory_on_finish(output_text: str):
            """Store the subagent's final output into its persistent memory."""
            if not task.memory_collection or not output_text:
                return
            try:
                from utim_cli.vector_memory import VectorMemory
                vm = VectorMemory(collection_name=task.memory_collection)
                vm.store(
                    document=output_text[:2000],
                    metadata={
                        "task_id": task.task_id,
                        "role": task.role,
                        "depth": this_depth,
                    }
                )
            except Exception:
                pass

        # ── Run subagent in its own thread ─────────────────────────────────
        def _run():
            try:
                session.run_task(
                    user_message=task.user_prompt,
                    max_iterations=task.max_iterations,
                    override_tools=filtered_tools,
                )
                for m in reversed(session.messages):
                    if m.get("role") == "assistant" and m.get("content"):
                        result_holder["output"] = m["content"]
                        break
                result_holder["iterations"] = getattr(session, "current_iteration", 0) + 1
            except Exception:
                result_holder["error"] = traceback.format_exc()

        run_thread = threading.Thread(
            target=_run,
            daemon=True,
            name=f"utim-subagent-d{this_depth}-{task.task_id}",
        )
        run_thread.start()
        run_thread.join(timeout=task.timeout_seconds)

        if run_thread.is_alive():
            sub_cancel.set()
            run_thread.join(timeout=5)
            result = SubAgentResult(
                task_id=task.task_id, role=task.role,
                success=False, output="",
                error=f"Timed out after {task.timeout_seconds}s.",
                elapsed_s=time.time() - t_start,
                depth=this_depth,
            )
        elif "error" in result_holder:
            result = SubAgentResult(
                task_id=task.task_id, role=task.role,
                success=False, output="",
                error=result_holder["error"],
                iterations=result_holder.get("iterations", 0),
                elapsed_s=time.time() - t_start,
                depth=this_depth,
            )
        else:
            output_text = result_holder.get("output", "(no output)")
            _store_memory_on_finish(output_text)
            result = SubAgentResult(
                task_id=task.task_id, role=task.role,
                success=True,
                output=output_text,
                iterations=result_holder.get("iterations", 0),
                elapsed_s=time.time() - t_start,
                depth=this_depth,
            )

    except Exception:
        result = SubAgentResult(
            task_id=task.task_id, role=task.role,
            success=False, output="",
            error=traceback.format_exc(),
            elapsed_s=time.time() - t_start,
            depth=this_depth,
        )

    sub_cancel.set()   # stop parent watcher thread

    # Thread-safe status update on the MAIN console
    icon  = "✓" if result.success else "✗"
    color = "green" if result.success else "red"
    depth_indent = "  " * (this_depth - 1)   # indent nested results visually
    depth_badge  = f"[dim]D{this_depth}[/dim]  " if this_depth > 1 else ""
    line = (
        f"{depth_indent}  [{color}]{icon}[/{color}]  "
        f"{depth_badge}"
        f"[bold]{result.role}[/bold] [dim]({result.task_id})[/dim]"
        f"  [dim]— {result.elapsed_s:.1f}s · {result.iterations} iter(s)[/dim]"
    )
    with status_lock:
        parent_console.print(line)

    return result


# ── SubAgentManager ───────────────────────────────────────────────────────────

class SubAgentManager:
    """
    Orchestrates parallel nested subagent execution and owns all UI rendering.

    Flow:
      1. Validate depth guard — block if at or beyond max nesting depth
      2. Print launch panel listing all tasks with their capabilities
      3. Submit all to ThreadPoolExecutor (cap MAX_PARALLEL)
      4. As each finishes → print indented ✓/✗ status line (thread-safe)
      5. When all done → print structured result panels
      6. Return formatted result string back to the calling agent
    """

    def __init__(
        self,
        parent_model:  str,
        console:       Console,
        cancel_event:  threading.Event,
        current_depth: int = 0,
    ):
        self.parent_model  = parent_model
        self.console       = console
        self.cancel_event  = cancel_event
        self.current_depth = current_depth

    def run_parallel(self, tasks: List[SubAgentTask]) -> List[SubAgentResult]:
        if not tasks:
            return []

        n = min(len(tasks), MAX_PARALLEL)

        # ── Launch panel ──────────────────────────────────────────────────
        self.console.print()
        depth_label = f"  [dim](depth {self.current_depth + 1})[/dim]" if self.current_depth > 0 else ""
        launch_table = Table.grid(padding=(0, 2))
        launch_table.add_column(style="dim cyan")
        launch_table.add_column()
        launch_table.add_column(style="dim")

        for task in tasks:
            model_label = task.model_id or self.parent_model
            if "/" in model_label:
                model_label = model_label.split("/")[-1]
            if model_label.endswith(":free"):
                model_label = model_label[:-5]

            caps = []
            if task.permission != "full":
                caps.append(f"perm:{task.permission}")
            if task.allowed_tools:
                caps.append(f"tools:{len(task.allowed_tools)}")
            if task.mcp_servers:
                caps.append(f"mcp:{','.join(task.mcp_servers[:2])}")
            if task.memory_collection:
                caps.append(f"mem:{task.memory_collection}")
            if task.max_depth > 0 and self.current_depth + 1 < min(task.max_depth, MAX_NEST_DEPTH):
                caps.append(f"nests→D{min(task.max_depth, MAX_NEST_DEPTH)}")

            caps_str = "  [dim cyan]" + "  ".join(caps) + "[/dim cyan]" if caps else ""
            launch_table.add_row(
                "⊛",
                f"[bold]{task.role}[/bold]  [dim]({task.task_id})[/dim]{caps_str}",
                f"{model_label} · max {task.max_iterations} iter · {task.timeout_seconds}s timeout",
            )

        indent = "  " * self.current_depth
        self.console.print(Panel(
            launch_table,
            title=(
                f"[bold cyan]Launching {len(tasks)} Subagent(s) in Parallel[/bold cyan]"
                f"{depth_label}"
            ),
            border_style="cyan",
            padding=(0, 1),
        ))
        self.console.print()

        # ── Parallel execution ────────────────────────────────────────────
        results: List[Optional[SubAgentResult]] = [None] * len(tasks)
        status_lock = threading.Lock()

        with ThreadPoolExecutor(
            max_workers=n,
            thread_name_prefix=f"utim-subagent-d{self.current_depth + 1}",
        ) as pool:
            future_map: Dict[Future, int] = {}
            for idx, task in enumerate(tasks):
                fut = pool.submit(
                    _run_subagent,
                    task,
                    self.parent_model,
                    self.cancel_event,
                    self.current_depth,
                    status_lock,
                    self.console,
                )
                future_map[fut] = idx

            for fut in as_completed(future_map):
                idx  = future_map[fut]
                task = tasks[idx]
                try:
                    results[idx] = fut.result()
                except Exception as exc:
                    results[idx] = SubAgentResult(
                        task_id=task.task_id, role=task.role,
                        success=False, output="", error=str(exc),
                        depth=self.current_depth + 1,
                    )

        # ── Result panels ─────────────────────────────────────────────────
        self.console.print()
        self.console.print(Rule("[dim]Subagent Results[/dim]", style="dim cyan"))

        for r in results:
            if r is None:
                continue
            if r.success:
                border  = "green"
                status  = "[green]✓ Done[/green]"
                content = Markdown(r.output[:3000])
            else:
                border  = "red"
                status  = "[red]✗ Failed[/red]"
                content = Text(r.error[:1000], style="red dim")

            depth_tag = f"  [dim]D{r.depth}[/dim]" if r.depth > 1 else ""
            self.console.print(Panel(
                content,
                title=(
                    f"[bold]{r.role}[/bold]  [dim]({r.task_id})[/dim]"
                    f"{depth_tag}  {status}"
                    f"  [dim]{r.elapsed_s:.1f}s · {r.iterations} iter(s)[/dim]"
                ),
                border_style=border,
                padding=(0, 1),
            ))

        self.console.print(Rule(style="dim cyan"))
        self.console.print()

        return results   # type: ignore[return-value]


# ── Result formatter ──────────────────────────────────────────────────────────

def format_subagent_results(results: List[SubAgentResult]) -> str:
    """
    Compact structured string fed back to the calling agent as the tool result.
    The agent reads this to synthesise a final response.
    """
    lines = [f"## Subagent Results  ({len(results)} task(s) completed)\n"]
    for r in results:
        status = "SUCCESS" if r.success else "FAILED"
        depth_tag = f"  [depth {r.depth}]" if r.depth > 1 else ""
        lines.append(
            f"### [{r.task_id}]  {r.role}{depth_tag}  —  {status}  "
            f"({r.elapsed_s:.1f}s, {r.iterations} iterations)"
        )
        if r.success:
            lines.append(f"\n{r.output}\n")
        else:
            lines.append(f"\n**Error:**\n```\n{r.error[:800]}\n```\n")
    return "\n".join(lines)
