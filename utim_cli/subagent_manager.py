"""
SubAgent Manager — Parallel Task Execution for UTIM CLI
========================================================

UI Design
---------
The main console shows a clean launch panel, a live per-subagent status
line that updates as each one finishes, and a final results panel.

Each subagent gets a SILENT (null) console so their internal tool-call
output (read_file, run_command, etc.) does NOT interleave in the main
terminal. Only the orchestration-level status lines are printed.

Architecture mirrors Antigravity's subagent system:

  Main Agent
     │
     ├─ calls invoke_subagents(tasks=[...])
     │
     └─► SubAgentManager
              │
              ├─ Prints launch panel
              ├─ ThreadPoolExecutor (max_workers = n_tasks, cap 8)
              │
              ├─ SubAgent 1 ──► silent console ──► Orchestrator ──► LLM
              ├─ SubAgent 2 ──► silent console ──► Orchestrator ──► LLM
              └─ SubAgent N ──► silent console ──► Orchestrator ──► LLM
              │
              ├─ As each finishes: prints ✓/✗ status line
              └─ Prints structured result panels when all done
              │
              └─ Returns result string to main agent as tool result

Design rules:
  - Each subagent has an ISOLATED console (no interleaving)
  - Max depth = 1 (enforced in _execute_tool, not here)
  - Results returned in ORDER of input tasks array
  - Parent cancel propagated to all subagent cancel events
  - Timeout per subagent configurable (default 300s)
"""

from __future__ import annotations

import io
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.table import Table
from rich.markdown import Markdown


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class SubAgentTask:
    """
    Specification for a single subagent run, provided by the main model.

    task_id         — Unique identifier  e.g. "research-1", "write-tests"
    role            — Human label        e.g. "Researcher", "Test Writer"
    system_prompt   — Full system prompt written by the main model
    user_prompt     — The actual task instruction for this subagent
    model_id        — Model to use (defaults to parent model if "")
    max_iterations  — Max LLM loops (default 20)
    timeout_seconds — Wall-clock timeout before cancellation (default 300)
    """
    task_id:          str
    role:             str
    system_prompt:    str
    user_prompt:      str
    model_id:         str  = ""
    max_iterations:   int  = 20
    timeout_seconds:  int  = 300


@dataclass
class SubAgentResult:
    """Result returned by a completed subagent."""
    task_id:    str
    role:       str
    success:    bool
    output:     str    # Final assistant response
    error:      str   = ""
    iterations: int   = 0
    elapsed_s:  float = 0.0


# ── Silent console ────────────────────────────────────────────────────────────

def _make_silent_console() -> Console:
    """
    Returns a Rich Console that writes to a StringIO buffer.
    Subagents use this so their internal tool-call output (read_file,
    run_command, etc.) doesn't interleave with the main terminal.
    """
    return Console(file=io.StringIO(), highlight=False, markup=True)


# ── SubAgent worker ───────────────────────────────────────────────────────────

def _run_subagent(
    task:         SubAgentTask,
    parent_model: str,
    cancel_event: threading.Event,
    depth:        int,
    status_lock:  threading.Lock,
    parent_console: Console,
) -> SubAgentResult:
    """
    Runs one subagent to completion inside a ThreadPoolExecutor worker.

    - Uses a silent console so output doesn't bleed into the main terminal.
    - Updates status via parent_console under status_lock when done.
    """
    t_start  = time.time()
    model_id = task.model_id or parent_model

    # Per-subagent cancel event
    sub_cancel = threading.Event()

    # Propagate parent cancellation
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

        session = Orchestrator(console=silent)
        session.model_id        = model_id
        session.cancel_event    = sub_cancel
        session._subagent_depth = depth + 1   # blocks recursive spawning

        # Isolated message history with subagent's own system prompt
        session.messages = [
            {"role": "system", "content": task.system_prompt},
        ]

        def _run():
            try:
                session.run_task(
                    user_message=task.user_prompt,
                    max_iterations=task.max_iterations,
                )
                for m in reversed(session.messages):
                    if m.get("role") == "assistant" and m.get("content"):
                        result_holder["output"] = m["content"]
                        break
                result_holder["iterations"] = getattr(session, "current_iteration", 0) + 1
            except Exception:
                result_holder["error"] = traceback.format_exc()

        run_thread = threading.Thread(target=_run, daemon=True,
                                      name=f"utim-subagent-{task.task_id}")
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
            )
        elif "error" in result_holder:
            result = SubAgentResult(
                task_id=task.task_id, role=task.role,
                success=False, output="",
                error=result_holder["error"],
                iterations=result_holder.get("iterations", 0),
                elapsed_s=time.time() - t_start,
            )
        else:
            result = SubAgentResult(
                task_id=task.task_id, role=task.role,
                success=True,
                output=result_holder.get("output", "(no output)"),
                iterations=result_holder.get("iterations", 0),
                elapsed_s=time.time() - t_start,
            )

    except Exception:
        result = SubAgentResult(
            task_id=task.task_id, role=task.role,
            success=False, output="",
            error=traceback.format_exc(),
            elapsed_s=time.time() - t_start,
        )

    sub_cancel.set()  # stop watcher

    # Thread-safe status update on the MAIN console
    icon  = "✓" if result.success else "✗"
    color = "green" if result.success else "red"
    line  = (
        f"  [{color}]{icon}[/{color}]  "
        f"[bold]{result.role}[/bold] [dim]({result.task_id})[/dim]"
        f"  [dim]— {result.elapsed_s:.1f}s · {result.iterations} iter(s)[/dim]"
    )
    with status_lock:
        parent_console.print(line)

    return result


# ── SubAgentManager ───────────────────────────────────────────────────────────

class SubAgentManager:
    """
    Orchestrates parallel subagent execution and owns all UI rendering.

    Flow:
      1. Print launch panel listing all tasks
      2. Submit all to ThreadPoolExecutor (cap 8)
      3. As each finishes → print ✓/✗ status line (thread-safe)
      4. When all done → print result panels per subagent
      5. Return formatted string to main agent
    """

    MAX_PARALLEL = 8

    def __init__(
        self,
        parent_model:  str,
        console:       Console,
        cancel_event:  threading.Event,
        depth:         int = 0,
    ):
        self.parent_model = parent_model
        self.console      = console
        self.cancel_event = cancel_event
        self.depth        = depth

    def run_parallel(self, tasks: List[SubAgentTask]) -> List[SubAgentResult]:
        if not tasks:
            return []

        n = min(len(tasks), self.MAX_PARALLEL)

        # ── Launch panel ──────────────────────────────────────────────────────
        self.console.print()
        launch_table = Table.grid(padding=(0, 2))
        launch_table.add_column(style="dim cyan")
        launch_table.add_column()
        launch_table.add_column(style="dim")
        for task in tasks:
            model_label = task.model_id or self.parent_model
            # Shorten model label
            if "/" in model_label:
                model_label = model_label.split("/")[-1]
            launch_table.add_row(
                "⊛",
                f"[bold]{task.role}[/bold]  [dim]({task.task_id})[/dim]",
                f"{model_label} · max {task.max_iterations} iter · {task.timeout_seconds}s timeout"
            )

        self.console.print(Panel(
            launch_table,
            title=f"[bold cyan]Launching {len(tasks)} Subagent(s) in Parallel[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))
        self.console.print()

        # ── Parallel execution ────────────────────────────────────────────────
        results: List[Optional[SubAgentResult]] = [None] * len(tasks)
        status_lock = threading.Lock()

        with ThreadPoolExecutor(
            max_workers=n,
            thread_name_prefix="utim-subagent"
        ) as pool:
            future_map: Dict[Future, int] = {}
            for idx, task in enumerate(tasks):
                fut = pool.submit(
                    _run_subagent,
                    task,
                    self.parent_model,
                    self.cancel_event,
                    self.depth,
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
                    )

        # ── Result panels ─────────────────────────────────────────────────────
        self.console.print()
        self.console.print(Rule("[dim]Subagent Results[/dim]", style="dim cyan"))

        for r in results:
            if r is None:
                continue
            if r.success:
                border  = "green"
                status  = "[green]✓ Done[/green]"
                content = Markdown(r.output[:3000])   # cap render length
            else:
                border  = "red"
                status  = "[red]✗ Failed[/red]"
                content = Text(r.error[:1000], style="red dim")

            self.console.print(Panel(
                content,
                title=(
                    f"[bold]{r.role}[/bold]  [dim]({r.task_id})[/dim]"
                    f"  {status}"
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
    Compact structured string fed back to the main model as the tool result.
    The main model reads this to synthesise a final answer.
    """
    lines = [f"## Subagent Results  ({len(results)} task(s) completed)\n"]
    for r in results:
        status = "SUCCESS" if r.success else "FAILED"
        lines.append(
            f"### [{r.task_id}]  {r.role}  —  {status}  "
            f"({r.elapsed_s:.1f}s, {r.iterations} iterations)"
        )
        if r.success:
            lines.append(f"\n{r.output}\n")
        else:
            lines.append(f"\n**Error:**\n```\n{r.error[:800]}\n```\n")
    return "\n".join(lines)
