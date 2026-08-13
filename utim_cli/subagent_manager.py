"""
SubAgent Manager — Nested Parallel Task Execution for UTIM CLI
==============================================================

Architecture (v2.3.1 — Full Parity)
-------------------------------------
Subagents use the SAME Orchestrator.__init__ as the main agent.
They inherit:
  - Identical context pruner (dynamic threshold, compression interval)
  - Identical compression logic (importance scoring, summarization)
  - Identical ReAct loop (run_task → _call_llm → _execute_tool)
  - Identical MCP client (selectively filtered by parent allowlist)
  - Identical skills system (scan_available_skills, RAG injection)
  - Identical experience memory (vector_memory RAG)
  - Identical brain watcher (architecture indexing)
  - Identical tool dispatch (all tools minus what parent blocks)
  - Identical token budget management per-model

Nesting:
  Main Agent  (depth 0)
     │
     ├─ invoke_subagents(tasks=[...])
     │
     └─► SubAgentManager
              │
              ├─ SubAgent A  (depth 1)  ──► full Orchestrator + own role
              │      │
              │      └─► SubAgent A1  (depth 2) ─► full Orchestrator + own role
              │
              └─ SubAgent B  (depth 1)  ──► full Orchestrator + own role

Main agent controls what each subagent can use:
  - allowed_mcp_servers  — which of the installed MCP servers are accessible
  - allowed_tools        — strict allowlist (if set, ONLY these are visible)
  - blocked_tools        — explicit denylist (stacks with permission profile)
  - permission           — named safety profile (full/read_only/no_shell/no_write/isolated)
  - allowed_skills       — which skill names are injectable into context

Design rules:
  - MAX_NEST_DEPTH = 10  (hard global ceiling)
  - Each subagent has an ISOLATED console (no output interleaving)
  - Each subagent has an ISOLATED message history
  - Parent cancel_event propagated recursively to all children
  - Timeout per subagent configurable (default 300s)
  - Results returned in ORDER of the input tasks array
  - Depth badge shown in terminal UI: D1, D2 … D10
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


# ── Constants ──────────────────────────────────────────────────────────────────

MAX_NEST_DEPTH = 10   # Hard global ceiling on recursive spawning
MAX_PARALLEL   = 8    # Max concurrent subagents at any single depth level


# ── Permission profiles ────────────────────────────────────────────────────────

#: Tools blocked under each named permission profile.
PERMISSION_PROFILES: Dict[str, Set[str]] = {
    # Full access — all enabled tools available (default)
    "full": set(),

    # Read-only — may not write files, execute commands, or delete
    "read_only": {
        "write_file", "apply_patch", "delete_file", "rename_file",
        "run_command", "run_script",
    },

    # No shell — may not execute any shell/subprocess commands
    "no_shell": {"run_command", "run_script"},

    # No write — may not modify or delete files; can run read-only commands
    "no_write": {
        "write_file", "apply_patch", "delete_file", "rename_file",
    },

    # Isolated — only memory and analysis; no filesystem or shell access
    "isolated": {
        "write_file", "apply_patch", "delete_file", "rename_file",
        "run_command", "run_script", "read_file", "list_directory",
        "search_files", "search_code",
    },
}


# ── Data models ────────────────────────────────────────────────────────────────

@dataclass
class SubAgentTask:
    """
    Specification for a single nested subagent run.

    Core fields (required by LLM)
    ─────────────────────────────
    task_id         — Unique identifier  e.g. "research-1", "write-tests"
    role            — Human label        e.g. "Researcher", "Test Writer"
    system_prompt   — Full custom system prompt (NOT inherited from parent)
    user_prompt     — The actual task instruction

    Execution settings
    ──────────────────
    model_id        — Model to use (defaults to parent model if "")
    max_iterations  — Max ReAct loop iterations (default 20)
    timeout_seconds — Wall-clock timeout before cancellation (default 300)

    Capability grants (controlled by parent)
    ────────────────────────────────────────
    allowed_tools       — If non-empty, ONLY these tools are visible (allowlist)
    blocked_tools       — Tool names explicitly blocked (stacks with permission)
    permission          — Named permission profile (see PERMISSION_PROFILES)
    allowed_mcp_servers — MCP server names this subagent may use from installed ones
                          [] = inherit all parent's active MCP servers
    allowed_skills      — Skill names this subagent may use from available skills
                          [] = all available skills (same as main agent)
    memory_collection   — ChromaDB collection for this subagent's persistent memory
                          "" = use same global experience memory as main agent
    max_depth           — How many further nesting levels this subagent may spawn
                          (0 = leaf node; capped at MAX_NEST_DEPTH)
    context_limit       — Optional hard cap on context tokens (0 = model default)
    """
    task_id:             str
    role:                str
    system_prompt:       str
    user_prompt:         str

    model_id:            str       = ""
    max_iterations:      int       = 20
    timeout_seconds:     int       = 300

    allowed_tools:       List[str] = field(default_factory=list)
    blocked_tools:       List[str] = field(default_factory=list)
    permission:          str       = "full"
    allowed_mcp_servers: List[str] = field(default_factory=list)
    allowed_skills:      List[str] = field(default_factory=list)
    memory_collection:   str       = ""
    max_depth:           int       = MAX_NEST_DEPTH
    context_limit:       int       = 0


@dataclass
class SubAgentResult:
    """Result returned by a completed subagent."""
    task_id:    str
    role:       str
    success:    bool
    output:     str
    error:      str   = ""
    iterations: int   = 0
    elapsed_s:  float = 0.0
    depth:      int   = 0


# ── Silent console ─────────────────────────────────────────────────────────────

def _make_silent_console() -> Console:
    """
    Returns a Rich Console that writes to a StringIO buffer.
    Subagents use this so their internal tool-call output (read_file,
    run_command, etc.) does NOT interleave with the main terminal.
    """
    return Console(file=io.StringIO(), highlight=False, markup=True)


# ── Tool filtering ─────────────────────────────────────────────────────────────

def _build_tool_list(
    task:         SubAgentTask,
    all_tools:    List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Produce the final tool list visible to this subagent by applying:
      1. Parent's globally disabled tools (from config)
      2. Permission profile block set
      3. Explicit blocked_tools
      4. Allowlist (if allowed_tools is non-empty)
    """
    from utim_cli.config import config as _cfg
    parent_disabled: Set[str] = set(_cfg.get("disabled_tools") or [])

    profile_blocked: Set[str] = PERMISSION_PROFILES.get(task.permission, set())
    extra_blocked:   Set[str] = set(task.blocked_tools)
    combined_blocked = parent_disabled | profile_blocked | extra_blocked

    filtered = [
        t for t in all_tools
        if t.get("function", {}).get("name") not in combined_blocked
    ]

    if task.allowed_tools:
        allowed_set = set(task.allowed_tools)
        filtered = [
            t for t in filtered
            if t.get("function", {}).get("name") in allowed_set
        ]

    return filtered


# ── MCP server filtering ───────────────────────────────────────────────────────

def _build_mcp_tools(task: SubAgentTask) -> List[Dict[str, Any]]:
    """
    Return MCP tools visible to this subagent.

    If allowed_mcp_servers is non-empty, only expose tools from those servers.
    Otherwise inherit all of the parent's active MCP server tools.
    """
    try:
        from utim_cli.mcp_client import mcp_manager
        all_mcp = mcp_manager.get_tools()
        if not task.allowed_mcp_servers:
            return all_mcp
        allowed = set(task.allowed_mcp_servers)
        return [
            t for t in all_mcp
            if t.get("_mcp_server", "") in allowed
        ]
    except Exception:
        return []


# ── Skills filtering ───────────────────────────────────────────────────────────

def _patch_skills_allowlist(session: Any, allowed_skills: List[str]) -> None:
    """
    If allowed_skills is non-empty, monkey-patch the session's
    skill-scanning function so only those skills are injectable.
    This is a lightweight override that wraps scan_available_skills
    and filters the result before it reaches get_system_prompt.
    """
    if not allowed_skills:
        return   # No restriction — use all available skills

    allowed_set = set(allowed_skills)

    try:
        import utim_cli.bootstrap as _bootstrap
        _orig = _bootstrap.scan_available_skills

        def _filtered_scan():
            all_skills = _orig()
            return {k: v for k, v in all_skills.items() if k in allowed_set}

        # Store the patch on the session so it can be reverted if needed
        session._orig_scan_available_skills = _orig
        _bootstrap.scan_available_skills = _filtered_scan
    except Exception:
        pass


def _restore_skills_patch(session: Any) -> None:
    """Restore the original scan_available_skills after the subagent finishes."""
    try:
        import utim_cli.bootstrap as _bootstrap
        orig = getattr(session, "_orig_scan_available_skills", None)
        if orig is not None:
            _bootstrap.scan_available_skills = orig
    except Exception:
        pass


# ── invoke_subagents schema (injected into subagents that may nest) ────────────

def _make_invoke_subagents_schema() -> Dict[str, Any]:
    """Return the OpenAI-style tool schema for invoke_subagents."""
    return {
        "type": "function",
        "function": {
            "name": "invoke_subagents",
            "description": (
                "Spawn one or more parallel nested subagents. Each subagent uses the full "
                "UTIM Orchestrator (same context pruner, same ReAct loop, same tool dispatch) "
                "but with its own role, system prompt, model, tools, MCP servers, and skills.\n\n"
                "All subagents run CONCURRENTLY. Results are returned when ALL complete.\n\n"
                "Rules:\n"
                "  • Write a full, specific system_prompt and user_prompt for EACH subagent\n"
                "  • Nesting is supported up to the global depth limit\n"
                "  • Max 8 subagents per invocation\n"
                "  • Results arrive in the same order as the tasks array"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "Array of subagent task specifications.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id":            {"type": "string"},
                                "role":               {"type": "string"},
                                "system_prompt":      {"type": "string"},
                                "user_prompt":        {"type": "string"},
                                "model_id":           {"type": "string"},
                                "max_iterations":     {"type": "integer"},
                                "timeout_seconds":    {"type": "integer"},
                                "allowed_tools":      {"type": "array", "items": {"type": "string"}},
                                "blocked_tools":      {"type": "array", "items": {"type": "string"}},
                                "permission":         {"type": "string", "enum": ["full", "read_only", "no_shell", "no_write", "isolated"]},
                                "allowed_mcp_servers":{"type": "array", "items": {"type": "string"}},
                                "allowed_skills":     {"type": "array", "items": {"type": "string"}},
                                "memory_collection":  {"type": "string"},
                                "max_depth":          {"type": "integer"},
                                "context_limit":      {"type": "integer"},
                            },
                            "required": ["task_id", "role", "system_prompt", "user_prompt"],
                        },
                        "minItems": 1,
                        "maxItems": 8,
                    }
                },
                "required": ["tasks"],
            },
        },
    }


# ── SubAgent worker ────────────────────────────────────────────────────────────

def _run_subagent(
    task:           SubAgentTask,
    parent_model:   str,
    cancel_event:   threading.Event,
    current_depth:  int,
    status_lock:    threading.Lock,
    parent_console: Console,
) -> SubAgentResult:
    """
    Runs one subagent to completion using the full UTIM Orchestrator.

    The subagent session is a genuine Orchestrator instance with:
      - Its own isolated message history (no parent history bleed)
      - Its own custom system prompt (role-specific, not inherited)
      - Its own model (can differ from parent)
      - Its own filtered tool set (governed by parent's grants)
      - Its own filtered MCP server access
      - Its own skills allowlist
      - Its own optional persistent memory collection
      - Same context pruner, same compression, same ReAct loop as main agent
    """
    t_start    = time.time()
    model_id   = task.model_id or parent_model
    this_depth = current_depth + 1

    # Per-subagent cancel event (propagated from parent)
    sub_cancel = threading.Event()

    def _watch_parent():
        while not cancel_event.is_set() and not sub_cancel.is_set():
            time.sleep(0.25)
        if cancel_event.is_set():
            sub_cancel.set()

    watcher = threading.Thread(target=_watch_parent, daemon=True,
                               name=f"utim-cancel-watcher-d{this_depth}-{task.task_id}")
    watcher.start()

    silent = _make_silent_console()
    result_holder: Dict[str, Any] = {}

    try:
        # ── Build the full Orchestrator (same as main agent) ──────────────
        from utim_cli.orchestrator import Orchestrator

        session = Orchestrator(console=silent)
        session.model_id     = model_id
        session.cancel_event = sub_cancel

        # ── Depth & nesting control ───────────────────────────────────────
        effective_max_depth = min(task.max_depth, MAX_NEST_DEPTH)
        session._subagent_depth     = this_depth
        session._subagent_max_depth = effective_max_depth

        # ── Context window override ───────────────────────────────────────
        if task.context_limit > 0:
            session._context_limit = task.context_limit
            # Recompute compression threshold against the hard cap
            session._compression_threshold = min(
                session._get_dynamic_threshold(),
                int(task.context_limit * 0.90),
            )

        # Recompute dynamic threshold and interval for the chosen model
        # (session.__init__ computed them for the parent's model; override now)
        session._compression_threshold = session._get_dynamic_threshold()
        session._compression_interval  = session._get_dynamic_interval()

        # ── Skills allowlist ──────────────────────────────────────────────
        _patch_skills_allowlist(session, task.allowed_skills)

        # ── Tool list (filtered by parent grants) ─────────────────────────
        from utim_cli.tools import get_tools as _get_tools
        utim_tools, _ = _get_tools()
        mcp_tools      = _build_mcp_tools(task)
        raw_tools      = utim_tools + mcp_tools
        filtered_tools = _build_tool_list(task, raw_tools)

        # Inject invoke_subagents if this subagent is allowed to nest further
        if this_depth < effective_max_depth:
            filtered_tools = [
                t for t in filtered_tools
                if t.get("function", {}).get("name") != "invoke_subagents"
            ]
            filtered_tools.append(_make_invoke_subagents_schema())

        # Store the filtered override on the session so _call_llm uses it
        session._subagent_tool_override = filtered_tools

        # ── Isolated message history with custom system prompt ────────────
        # Build a proper subagent system prompt using the same get_system_prompt
        # machinery so MCP/skills/experience context is correctly wired, then
        # PREPEND the parent-specified role system prompt.
        from utim_cli.orchestrator import get_system_prompt as _gsp
        base_sys = _gsp(user_prompt=task.user_prompt)

        # Optional: query persistent memory for this subagent's collection
        memory_context = ""
        if task.memory_collection:
            try:
                from utim_cli.vector_memory import VectorMemory
                vm      = VectorMemory(collection_name=task.memory_collection)
                results = vm.query(task.user_prompt, n_results=5)
                if results:
                    lines = [f"\n\n### Persistent Memory ({task.memory_collection}) ###"]
                    for r in results:
                        doc = r.get("document", "")
                        if doc:
                            lines.append(f"- {doc[:500]}")
                    memory_context = "\n".join(lines)
            except Exception:
                pass

        # Role system prompt from parent goes FIRST (highest priority),
        # then UTIM's full base system prompt (MCP + skills + experience),
        # then any persistent memory context for this subagent.
        full_system_prompt = (
            f"### YOUR ROLE ###\n{task.system_prompt}\n\n"
            f"### UTIM AGENT FRAMEWORK ###\n{base_sys}"
            f"{memory_context}"
        )

        session.messages = [
            {"role": "system", "content": full_system_prompt},
        ]

        # ── Store memory on completion ────────────────────────────────────
        def _store_memory(output_text: str) -> None:
            if not task.memory_collection or not output_text:
                return
            try:
                from utim_cli.vector_memory import VectorMemory
                vm = VectorMemory(collection_name=task.memory_collection)
                vm.store(
                    document=output_text[:2000],
                    metadata={
                        "task_id": task.task_id,
                        "role":    task.role,
                        "depth":   this_depth,
                        "model":   model_id,
                    },
                )
            except Exception:
                pass

        # ── Run the subagent ReAct loop ───────────────────────────────────
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
            finally:
                _restore_skills_patch(session)

        run_thread = threading.Thread(
            target=_run, daemon=True,
            name=f"utim-subagent-d{this_depth}-{task.task_id}",
        )
        run_thread.start()
        run_thread.join(timeout=task.timeout_seconds)

        if run_thread.is_alive():
            sub_cancel.set()
            run_thread.join(timeout=5)
            result = SubAgentResult(
                task_id=task.task_id, role=task.role, success=False, output="",
                error=f"Timed out after {task.timeout_seconds}s.",
                elapsed_s=time.time() - t_start, depth=this_depth,
            )
        elif "error" in result_holder:
            result = SubAgentResult(
                task_id=task.task_id, role=task.role, success=False, output="",
                error=result_holder["error"],
                iterations=result_holder.get("iterations", 0),
                elapsed_s=time.time() - t_start, depth=this_depth,
            )
        else:
            out = result_holder.get("output", "(no output)")
            _store_memory(out)
            result = SubAgentResult(
                task_id=task.task_id, role=task.role, success=True, output=out,
                iterations=result_holder.get("iterations", 0),
                elapsed_s=time.time() - t_start, depth=this_depth,
            )

    except Exception:
        result = SubAgentResult(
            task_id=task.task_id, role=task.role, success=False, output="",
            error=traceback.format_exc(),
            elapsed_s=time.time() - t_start, depth=this_depth,
        )

    sub_cancel.set()   # stop parent watcher

    # ── Thread-safe status update on MAIN console ─────────────────────────
    icon   = "✓" if result.success else "✗"
    color  = "green" if result.success else "red"
    indent = "  " * (this_depth - 1)
    badge  = f"[dim]D{this_depth}[/dim]  " if this_depth > 1 else ""
    line   = (
        f"{indent}  [{color}]{icon}[/{color}]  "
        f"{badge}[bold]{result.role}[/bold] [dim]({result.task_id})[/dim]"
        f"  [dim]— {result.elapsed_s:.1f}s · {result.iterations} iter(s)[/dim]"
    )
    with status_lock:
        parent_console.print(line)

    return result


# ── SubAgentManager ────────────────────────────────────────────────────────────

class SubAgentManager:
    """
    Orchestrates parallel nested subagent execution and owns all UI rendering.

    Flow:
      1. Depth guard — block if at or beyond global max
      2. Print launch panel listing all tasks with their capability grants
      3. Submit all to ThreadPoolExecutor (cap MAX_PARALLEL)
      4. As each finishes → print indented ✓/✗ status line (thread-safe)
      5. When all done → print structured result panels
      6. Return formatted string back to the calling agent
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
        next_depth = self.current_depth + 1

        # ── Launch panel ──────────────────────────────────────────────────
        self.console.print()
        depth_tag = f"  [dim](depth {next_depth})[/dim]" if self.current_depth > 0 else ""
        launch_table = Table.grid(padding=(0, 2))
        launch_table.add_column(style="dim cyan")
        launch_table.add_column()
        launch_table.add_column(style="dim")

        for task in tasks:
            model_label = task.model_id or self.parent_model
            if "/" in model_label:
                model_label = model_label.split("/")[-1]
            model_label = model_label.removesuffix(":free")

            caps = []
            if task.permission != "full":
                caps.append(f"perm:{task.permission}")
            if task.allowed_tools:
                caps.append(f"tools:{len(task.allowed_tools)}")
            if task.allowed_mcp_servers:
                caps.append(f"mcp:{','.join(task.allowed_mcp_servers[:2])}")
            if task.allowed_skills:
                caps.append(f"skills:{len(task.allowed_skills)}")
            if task.memory_collection:
                caps.append(f"mem:{task.memory_collection}")
            effective_max = min(task.max_depth, MAX_NEST_DEPTH)
            if next_depth < effective_max:
                caps.append(f"nests→D{effective_max}")

            caps_str = (
                "  [dim cyan]" + "  ".join(caps) + "[/dim cyan]" if caps else ""
            )
            launch_table.add_row(
                "⊛",
                f"[bold]{task.role}[/bold]  [dim]({task.task_id})[/dim]{caps_str}",
                f"{model_label} · max {task.max_iterations} iter · {task.timeout_seconds}s timeout",
            )

        self.console.print(Panel(
            launch_table,
            title=(
                f"[bold cyan]Launching {len(tasks)} Subagent(s) in Parallel[/bold cyan]"
                f"{depth_tag}"
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
            thread_name_prefix=f"utim-subagent-d{next_depth}",
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
                        depth=next_depth,
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

            depth_badge = f"  [dim]D{r.depth}[/dim]" if r.depth > 1 else ""
            self.console.print(Panel(
                content,
                title=(
                    f"[bold]{r.role}[/bold]  [dim]({r.task_id})[/dim]"
                    f"{depth_badge}  {status}"
                    f"  [dim]{r.elapsed_s:.1f}s · {r.iterations} iter(s)[/dim]"
                ),
                border_style=border,
                padding=(0, 1),
            ))

        self.console.print(Rule(style="dim cyan"))
        self.console.print()

        return results  # type: ignore[return-value]


# ── Result formatter ───────────────────────────────────────────────────────────

def format_subagent_results(results: List[SubAgentResult]) -> str:
    """
    Compact structured string fed back to the calling agent as the tool result.
    """
    lines = [f"## Subagent Results  ({len(results)} task(s) completed)\n"]
    for r in results:
        status    = "SUCCESS" if r.success else "FAILED"
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
