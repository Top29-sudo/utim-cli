import typer
import sys
import os
import locale
import warnings
import logging
from typing import Optional, List, Dict, Any
from utim_cli.constants import DEFAULT_MODEL, PROMPT_SYMBOL, ARROW_SYMBOL

# Suppress HuggingFace / SentenceTransformers warnings, progress bars, and log messages globally
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PROMPT_TOOLKIT_NO_CPR"] = "1"

warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub.*")
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
# Suppress httpx request logs from Hugging Face model downloads
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)


# Auto-detect if executed via utimlite command (pip script, npx, or cmd wrapper)
_entry_script = os.path.basename(sys.argv[0] if sys.argv else "").lower()
if "utimlite" in _entry_script:
    os.environ["UTIM_LITE_MODE"] = "1"

if os.name == 'nt':
    try:
        import ctypes
        # Set Windows console input and output code pages to UTF-8 (65001) programmatically
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    os.system('chcp 65001 >nul 2>&1')
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
            
            # Enable VT input mode on Windows 10/11 to support full emoji pasting and surrogate pair inputs
            h_in = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(h_in, ctypes.byref(mode)):
                ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
                kernel32.SetConsoleMode(h_in, mode.value | ENABLE_VIRTUAL_TERMINAL_INPUT)
        except Exception:
            pass

    # Set locale to UTF-8 for proper emoji rendering on Windows
    try:
        locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except locale.Error:
            pass  # Fallback to default locale

# Force UTF-8 encoding for stdout/stderr to fix emoji rendering on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure stdin is also UTF-8
if hasattr(sys.stdin, "reconfigure"):
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except:
        pass
if hasattr(sys, "__stdin__") and sys.__stdin__ and hasattr(sys.__stdin__, "reconfigure"):
    try:
        sys.__stdin__.reconfigure(encoding="utf-8")
    except:
        pass
import shutil
import signal
import threading
import time
import requests
import json
import re
import nest_asyncio
nest_asyncio.apply()

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from rich.markdown import Markdown
from rich.markup import escape

from prompt_toolkit import Application
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.layout import Layout, ConditionalContainer, HSplit, VSplit, Window, FloatContainer, Float
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.layout.processors import Processor, Transformation

_MAIN_LOOP = None

def _run_in_terminal_safe(func):
    """Safely call run_in_terminal from either the main event loop thread or a background thread.
    
    If on the main thread, we call run_in_terminal(func) and let it run asynchronously
    without blocking (which would cause a deadlock).
    If on a background thread, we schedule the call to run on the main thread's event loop
    and wait for it to complete.
    """
    global _MAIN_LOOP
    import asyncio

    # Try to get the running loop in the current thread
    try:
        loop = asyncio.get_running_loop()
        on_loop_thread = True
        _MAIN_LOOP = loop
    except RuntimeError:
        on_loop_thread = False

    def _invalidate_app():
        """Force prompt_toolkit to fully redraw the screen after the dialog exits."""
        try:
            from prompt_toolkit.application.current import get_app
            app = get_app()
            app.invalidate()
        except Exception:
            pass

    if on_loop_thread:
        # We are on the main loop thread. Just call run_in_terminal.
        # Wrap it in ensure_future so it is scheduled and run on the loop.
        async def _run_and_invalidate():
            await run_in_terminal(func)
            _invalidate_app()
        asyncio.ensure_future(_run_and_invalidate())
    else:
        # We are on a background thread.
        # Schedule the coroutine on the main loop thread and block until it finishes.
        loop = _MAIN_LOOP
        if loop and loop.is_running():
            async def _run_async():
                await run_in_terminal(func)
                _invalidate_app()
            future = asyncio.run_coroutine_threadsafe(_run_async(), loop)
            try:
                # Wait indefinitely for the user to make a choice (no 30s timeout)
                future.result()
            except Exception:
                pass
        else:
            # Fallback if no loop is running: just call the function directly.
            # This path is only hit if pt_app hasn't started yet (e.g. during login).
            try:
                func()
            except (KeyboardInterrupt, EOFError):
                pass
            except Exception:
                pass

def _run_full_screen_flow(fn, *args, **kwargs):
    """Run a blocking Rich-console function inside its own full-screen PTK Application.

    This prevents sub-flows (payment, readme, install, quota-share, etc.) from
    printing straight to stdout (the chat stream) when no PTK app is active.

    How it works:
      1. A background thread runs `fn(*args, **kwargs)` which does console.print()
         and input() calls normally.
      2. A minimal full-screen PTK Application takes ownership of the terminal
         while the thread runs, so all output is contained inside the TUI layer.
      3. The PTK app exits automatically once the thread finishes.

    The function must accept a Rich Console as its first positional argument
    OR accept **kwargs; the console is passed via the args/kwargs the caller provides.
    """
    import asyncio
    from prompt_toolkit import Application as _App
    from prompt_toolkit.layout import Layout as _Layout, Window as _Win
    from prompt_toolkit.layout.controls import FormattedTextControl as _FTC
    from prompt_toolkit.key_binding import KeyBindings as _KB
    from prompt_toolkit.input import create_input
    from prompt_toolkit.output import create_output

    _done = threading.Event()
    _exc  = [None]

    def _worker():
        try:
            # Call fn directly — do NOT wrap in _run_in_terminal_safe here.
            # fn's internal _prompt_text calls will each issue their own
            # _run_in_terminal_safe per step. Wrapping the whole fn would
            # cause nested run_in_terminal, which deadlocks after Step 1.
            fn(*args, **kwargs)
        except Exception as e:
            _exc[0] = e
        finally:
            _done.set()
            # Signal the PTK app to exit once the worker is done
            try:
                _app_ref[0].exit()
            except Exception:
                pass

    kb = _KB()

    @kb.add('c-c')
    @kb.add('escape')
    def _force_quit(e):
        _done.set()
        try:
            e.app.exit()
        except Exception:
            pass

    _app_ref = [None]

    app = _App(
        layout=_Layout(_Win(FormattedTextControl(lambda: []))),
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
    )
    _app_ref[0] = app

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    try:
        app.run()
    except Exception:
        pass
    t.join(timeout=120)
    if _exc[0]:
        raise _exc[0]


class PlaceholderProcessor(Processor):
    def __init__(self, placeholder_text: str, style: str = "class:placeholder"):
        self.placeholder_text = placeholder_text
        self.style = style

    def apply_transformation(self, transformation_input):
        if not transformation_input.document.text and transformation_input.lineno == 0:
            return Transformation(
                transformation_input.fragments + [
                    (self.style, self.placeholder_text)
                ]
            )
        return Transformation(transformation_input.fragments)

from .orchestrator import Orchestrator
from .config import config
from . import auth

# Server URL - Default to production if available (can be set via env, disabled for local mode)
SERVER_URL = os.getenv("UTIM_SERVER_URL", "")  # Empty string disables server calls for local mode

# ─── Color constants for consolidated 3-color palette ───────────────────────
PURPLE = "#cba6f7"
BLUE = "#42bcf5"
YELLOW = "#f9e2af"

# ─── Rich Theme ───────────────────────────────────────────────────────────────
custom_theme = Theme({
    "info":    "dim cyan",
    "warning": "bold yellow",
    "danger":  "bold red",
    "success": "bold green",
    "muted":   "dim white",
    "accent":  BLUE,
    "purple":  PURPLE,
})
# ─── Console Initialization ──────────────────────────────────────────────────
import shutil

# Capture the REAL stdout once at module load time, before prompt_toolkit or Rich
# can replace sys.stdout with a proxy. This reference is used by _StdoutProxy
# to write directly to the terminal without going through any proxy chain.
_REAL_STDOUT = sys.stdout

def get_console_width():
    # Try to get real terminal width, default to 80 if fails
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


class _StdoutProxy:
    """Thin wrapper that writes to the real underlying stdout handle, unwrapping
    any Rich FileProxy loops to prevent recursion, but letting prompt_toolkit's
    patch_stdout proxy do its magic to avoid display corruption.
    """
    def write(self, s):
        target = sys.stdout
        while hasattr(target, "rich_proxied_file"):
            target = getattr(target, "rich_proxied_file")
        if hasattr(target, "write"):
            target.write(s)
        else:
            _REAL_STDOUT.write(s)

    def flush(self):
        target = sys.stdout
        while hasattr(target, "rich_proxied_file"):
            target = getattr(target, "rich_proxied_file")
        if hasattr(target, "flush"):
            target.flush()
        else:
            _REAL_STDOUT.flush()

    def fileno(self):
        target = sys.stdout
        while hasattr(target, "rich_proxied_file"):
            target = getattr(target, "rich_proxied_file")
        if hasattr(target, "fileno"):
            try:
                return target.fileno()
            except Exception:
                pass
        return _REAL_STDOUT.fileno()

    @property
    def encoding(self):
        target = sys.stdout
        while hasattr(target, "rich_proxied_file"):
            target = getattr(target, "rich_proxied_file")
        return getattr(target, "encoding", "utf-8")

    @property
    def errors(self):
        target = sys.stdout
        while hasattr(target, "rich_proxied_file"):
            target = getattr(target, "rich_proxied_file")
        return getattr(target, "errors", "replace")

    def isatty(self):
        return True   # force_terminal=True already set; keep tty-detection happy

console = Console(
    theme=custom_theme,
    highlight=False,
    force_terminal=True,
    width=get_console_width(),
    file=_StdoutProxy(),
)



def render_usage_menu(data: dict, con=console):
    if not isinstance(data, dict):
        data = {}
    data = dict(data)
    for k in ["balance", "max_limit", "percent_remaining", "refill_rate", "bonus_balance", "bonus_quota_percent", "bonus_limit", "free_monthly_cap", "five_hour_quota_percent", "quota_bank_percent"]:
        if data.get(k) is None:
            data[k] = 0.0
    for k in ["refills_in_seconds", "refills_processed", "max_refills"]:
        if data.get(k) is None:
            data[k] = 0

    is_subscribed = data.get("is_subscribed", False)
    plan_name = data.get("plan_name", "Free")
    balance = data.get("balance")
    max_limit = data.get("max_limit")
    percent = data.get("percent_remaining")
    refills_in = data.get("refills_in_seconds")
    refills_processed = data.get("refills_processed")
    max_refills = data.get("max_refills")
    refill_rate = data.get("refill_rate")

    bar_width = 40
    filled = int(round((percent / 100.0) * bar_width))
    filled = min(bar_width, max(0, filled))

    hours   = refills_in // 3600
    minutes = (refills_in % 3600) // 60
    time_str = f"{hours}h {minutes}m" if refills_in > 0 else "Now"

    from utim_cli.config import config
    preferred_quota = config.get("preferred_quota", "regular")

    import os, json
    from utim_cli.config import get_utim_dir as _get_utim_dir
    model_id = DEFAULT_MODEL
    state_file = _get_utim_dir() / "session_state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if "model_id" in saved:
                    model_id = saved["model_id"]
        except Exception:
            pass

    con.print()
    con.print(f"[bold white]Preferred Quota to use:[/bold white] [bold cyan]{preferred_quota}[/bold cyan] [dim](run '/quota' to change)[/dim]\n")

    if not is_subscribed:
        # ── Free tier: 2 bars only — 5h Refill + Bonus ──────────────────
        bonus_balance = data.get("bonus_balance", 0.0)
        bonus_pct     = data.get("bonus_quota_percent", 0.0)
        bonus_limit   = data.get("bonus_limit", data.get("max_limit", 0.0))
        free_monthly_remaining = data.get("free_monthly_remaining", None)
        FREE_MONTHLY_CAP = data.get("free_monthly_cap", 3000.0)

        # Bar 1: 5-Hour Refill
        filled_5h = int(round((percent / 100.0) * bar_width))
        filled_5h = min(bar_width, max(0, filled_5h))
        con.print(f"[bold white]5-Hour Refill Quota (Free Plan)[/bold white]")
        con.print(f"  [[bold green]{'█'*filled_5h}[/bold green][dim]{'░'*(bar_width-filled_5h)}[/dim]] [bold white]{percent:.1f}%[/bold white]")
        con.print(f"  [bold green]{balance:.1f} / {max_limit:.0f} credits[/bold green]  [dim]· refills [bold yellow]{refill_rate:.0f}[/bold yellow] credits in [bold yellow]{time_str}[/bold yellow] · no stacking[/dim]")
        if free_monthly_remaining is not None and free_monthly_remaining > 0:
            monthly_used = max(0.0, FREE_MONTHLY_CAP - free_monthly_remaining)
            monthly_pct = min(100.0, (monthly_used / FREE_MONTHLY_CAP) * 100.0) if FREE_MONTHLY_CAP > 0 else 0.0
            con.print(f"  [dim]Monthly allowance used: [bold cyan]{monthly_used:.0f}[/bold cyan] / [bold white]{FREE_MONTHLY_CAP:.0f}[/bold white] credits  ([bold yellow]{free_monthly_remaining:.0f}[/bold yellow] remaining)[/dim]")
        elif free_monthly_remaining is not None and free_monthly_remaining <= 0:
            con.print(f"  [bold red]Monthly allowance EXHAUSTED: {FREE_MONTHLY_CAP:.0f} / {FREE_MONTHLY_CAP:.0f} credits used.[/bold red]")
            con.print(f"  [dim red]No more requests allowed until the monthly cycle resets.[/dim red]")
            con.print(f"  [dim]Run [bold]utim upgrade[/bold] or visit [bold]utim.dev/pricing[/bold] to increase your limit.[/dim]")

        con.print()

        # Bar 2: Bonus (Via Pay As You Go)
        filled_bonus = int(round((bonus_pct / 100.0) * bar_width))
        filled_bonus = min(bar_width, max(0, filled_bonus))
        if bonus_balance > 0.0:
            bonus_color = "bold green"
            bonus_note  = "[bold #e5ff00]✦ Premium models UNLOCKED[/bold #e5ff00] while bonus lasts"
        else:
            bonus_color = "dim"
            bonus_note  = "[dim]Top up via Pay As You Go to unlock premium models[/dim]"
        con.print(f"[bold white]Bonus Quota (Via Pay As You Go)[/bold white]")
        con.print(f"  [[{bonus_color}]{'█'*filled_bonus}[/{bonus_color}][dim]{'░'*(bar_width-filled_bonus)}[/dim]] [bold white]{bonus_pct:.1f}%[/bold white]")
        con.print(f"  [dim]Credits available: [bold green]{bonus_balance:.1f}[/bold green]  Max Credits allowed: [bold white]{bonus_limit:.0f}[/bold white][/dim]")
        con.print(f"  {bonus_note}")

        # Premium model warning for Free Plan users prioritizing regular quota
        if ":free" not in model_id and preferred_quota == "regular":
            con.print()
            con.print(
                "[bold red]Warning: With your current plan you can't use premium models with your quota provided by the free plan. "
                "if u want to use premium models on UTIM provided quota please upgrade your plan or please use your bonus quota[/bold red]"
            )
    else:
        # Paid tiers: percentages only, no misleading raw credits
        five_hour_pct = data.get("five_hour_quota_percent", percent)
        quota_bank_pct = data.get("quota_bank_percent", percent)

        # 5h quota bar
        filled_5h = int(round((five_hour_pct / 100.0) * bar_width))
        filled_5h = min(bar_width, max(0, filled_5h))

        # Quota bank bar
        filled_bank = int(round((quota_bank_pct / 100.0) * bar_width))
        filled_bank = min(bar_width, max(0, filled_bank))

        con.print(f"[bold white]Five Hour Quota ({plan_name} Plan)[/bold white]")
        con.print(f"  [[bold green]{'█'*filled_5h}[/bold green][dim]{'░'*(bar_width-filled_5h)}[/dim]] [bold white]{five_hour_pct:.2f}%[/bold white]")
        con.print(f"  [dim]Resets in [bold yellow]{time_str}[/bold yellow] (Refills [bold cyan]{refill_rate:.2f}[/bold cyan] credits per 5h slot)[/dim]")
        con.print()

        con.print(f"[bold white]Quota Bank[/bold white]")
        con.print(f"  [[bold green]{'█'*filled_bank}[/bold green][dim]{'░'*(bar_width-filled_bank)}[/dim]] [bold white]{quota_bank_pct:.2f}%[/bold white]")
        con.print(f"  [dim]Unused 5-hour quota automatically rolls over into the bank.[/dim]")
        con.print()
        
        # ── Unallocated Monthly Quota bar (paid subscribers only) ─────────────
        _refill_rate = data.get("refill_rate", 0.0)
        _refills_processed = data.get("refills_processed", 0)
        _max_refills = data.get("max_refills", 144) or 144
        _regular_plan_credits = _refill_rate * _max_refills
        if _regular_plan_credits > 0:
            _quota_bank = (data.get("quota_bank_percent", 0.0) / 100.0) * (_regular_plan_credits * 2.0)
            _cycle_allow = _regular_plan_credits / 144.0
            _allocated_to_cycles = _refills_processed * _cycle_allow
            _five_h_pct = data.get("five_hour_quota_percent", 0.0)
            _current_cycle_used = _cycle_allow * (1.0 - _five_h_pct / 100.0)
            _unallocated = max(0.0, _regular_plan_credits - _allocated_to_cycles - max(0.0, balance) - _current_cycle_used)
            _remaining_cycles = max(1, _max_refills - _refills_processed)
            _per_cycle = _unallocated / _remaining_cycles if _remaining_cycles > 0 else 0.0
            _unallocated_pct = min(100.0, max(0.0, (_unallocated / _regular_plan_credits) * 100.0)) if _regular_plan_credits > 0 else 0.0
            filled_ua = int(round((_unallocated_pct / 100.0) * bar_width))
            filled_ua = min(bar_width, max(0, filled_ua))
            ua_color = "bold green" if _unallocated_pct >= 50 else ("bold yellow" if _unallocated_pct >= 20 else "bold red")
            con.print(f"[bold white]Unallocated Monthly Quota ({plan_name})[/bold white]")
            con.print(f"  [[{ua_color}]{'█'*filled_ua}[/{ua_color}][dim]{'░'*(bar_width-filled_ua)}[/dim]] [{ua_color}]{_unallocated_pct:.2f}%[/{ua_color}]")
            con.print(f"  [dim]{_unallocated:,.0f} / {_regular_plan_credits:,.0f} credits[/dim]  [dim]· {_unallocated_pct:.2f}% remaining · {_remaining_cycles} cycles left · {_per_cycle:,.2f} credits per cycle[/dim]")
            con.print()

        bonus_quota_pct = data.get("bonus_quota_percent", 0.0)
        filled_bonus = int(round((bonus_quota_pct / 100.0) * bar_width))
        filled_bonus = min(bar_width, max(0, filled_bonus))
        bonus_balance = data.get("bonus_balance", 0.0)
        bonus_limit = data.get("bonus_limit", 0.0)
        
        con.print(f"[bold white]Bonus Quota[/bold white]")
        con.print(f"  [[bold green]{'█'*filled_bonus}[/bold green][dim]{'░'*(bar_width-filled_bonus)}[/dim]] [bold white]{bonus_quota_pct:.2f}%[/bold white]")
        con.print(f"  [dim]Credits available: [bold green]{bonus_balance:.1f}[/bold green]  Max Credits allowed: [bold white]{bonus_limit:.0f}[/bold white][/dim]")
    con.print()
    
    # ── Current Session Usage Breakdown ─────────────────────────────────────
    try:
        from utim_cli.client_utils import get_session_usage
        usage_data = get_session_usage()  # auto-resolves current session_id

        main_in   = usage_data.get("main_agent_input_tokens", 0)
        main_out  = usage_data.get("main_agent_output_tokens", 0)
        main_cost = usage_data.get("main_agent_credits", 0.0)

        tool_in   = usage_data.get("tools_input_tokens", 0)
        tool_out  = usage_data.get("tools_output_tokens", 0)
        tool_cost = usage_data.get("tools_credits", 0.0)

        total_tokens = main_in + main_out + tool_in + tool_out
        total_cost   = main_cost + tool_cost

        # Show the breakdown whenever any tokens have been tracked
        if total_tokens > 0 or total_cost > 0:
            con.print(f"[bold white]Current Session Usage Breakdown[/bold white]")

            # Main Agent row — show even if cost rounds to 0 as long as tokens exist
            if main_in > 0 or main_out > 0 or main_cost > 0:
                main_pct = (main_cost / total_cost * 100) if total_cost > 0 else 0.0
                con.print(
                    f"  [bold cyan]Main Agent:[/bold cyan]"
                    f"  [bold white]{main_cost:.4f}[/bold white] credits"
                    + (f"  [dim]({main_pct:.1f}%)[/dim]" if total_cost > 0 else "")
                )
                con.print(f"    [dim]Tokens: {main_in:,} in · {main_out:,} out[/dim]")

            # Tools / Subagents row
            if tool_in > 0 or tool_out > 0 or tool_cost > 0:
                tool_pct = (tool_cost / total_cost * 100) if total_cost > 0 else 0.0
                con.print(
                    f"  [bold yellow]Tools / Subagents:[/bold yellow]"
                    f"  [bold white]{tool_cost:.4f}[/bold white] credits"
                    + (f"  [dim]({tool_pct:.1f}%)[/dim]" if total_cost > 0 else "")
                )
                con.print(f"    [dim]Tokens: {tool_in:,} in · {tool_out:,} out[/dim]")

            # Total row
            total_in  = main_in + tool_in
            total_out = main_out + tool_out
            con.print(f"  [dim]─────────────────────────────────────────────[/dim]")
            con.print(
                f"  [bold white]Total this session:[/bold white]"
                f"  [bold #42bcf5]{total_cost:.4f}[/bold #42bcf5] credits"
            )
            con.print(f"    [dim]Tokens: {total_in:,} in · {total_out:,} out[/dim]")
            con.print()
        else:
            con.print("[dim]  No usage recorded yet for the current session.[/dim]")
            con.print()
    except Exception:
        pass

def _run_usage_dialog(data: dict):
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style as PTStyle
    from prompt_toolkit.formatted_text import ANSI
    from rich.console import Console
    import shutil
    
    # 1. Capture the Rich-rendered usage panel to ANSI text
    width = min(80, get_console_width())
    capture_console = Console(
        theme=custom_theme,
        highlight=False,
        force_terminal=True,
        color_system="truecolor",
        width=width
    )
    
    with capture_console.capture() as capture:
        capture_console.print()
        capture_console.print("=" * width, style="dim")
        capture_console.print(" UTIM CLI — COMPUTE QUOTA & USAGE STATS ", style="bold #42bcf5", justify="center")
        capture_console.print("=" * width, style="dim")
        
        render_usage_menu(data, capture_console)
        
        capture_console.print()
        capture_console.print("  [bold white]How the Quota System works:[/bold white]")
        if not data.get("is_subscribed", False):
            capture_console.print("  • [bold #42bcf5]5-Hour Refill Quota[/bold #42bcf5]: Refills 100 credits every 5 hours (no stacking).")
            capture_console.print("    Monthly allowance is 3,000 credits. Resets every 30-day billing cycle.")
            capture_console.print("  • [bold #42bcf5]Bonus Quota (Via Pay As You Go)[/bold #42bcf5]: Credits from top-ups go here.")
            capture_console.print("    Bonus unlocks [bold #e5ff00]all premium models[/bold #e5ff00] instantly. Used first before 5h quota.")
            capture_console.print("    When bonus runs out, premium models lock — restart UTIM to switch back to free models.")
        else:
            capture_console.print("  • [bold #42bcf5]Five Hour Quota[/bold #42bcf5]: Credits allocated in rolling 5-hour slots.")
            capture_console.print("    Unused slot credits automatically roll over into the Quota Bank.")
            capture_console.print("  • [bold #42bcf5]Quota Bank[/bold #42bcf5]: Unused 5h slot credits roll over here automatically.")
            capture_console.print("    Stores up to 2 months' capacity. Used if active 5h slot is depleted.")
            capture_console.print("  • [bold #42bcf5]Unallocated Monthly Quota[/bold #42bcf5]: Regular plan credits reserved for future 5-hour cycles.")
            capture_console.print("    Deducted when you use /quotashare to send credits to referred users.")
            capture_console.print("  • [bold #42bcf5]Bonus Quota[/bold #42bcf5]: Earned when downgrading (halved remaining balance).")
            capture_console.print("    Stagnant, does not expire, and is consumed first.")
            capture_console.print("  • [bold #42bcf5]Deduction Priority[/bold #42bcf5]: 1. Bonus Quota  →  2. Five Hour Quota  →  3. Quota Bank")
        capture_console.print()
        
        capture_console.print("-" * width, style="dim")
        capture_console.print(" ↑/↓ scroll · PageUp/PageDown jump · ESC/Q close ", style="italic dim", justify="center")
        capture_console.print("-" * width, style="dim")
        capture_console.print()

    ansi_text = capture.get()

    # 2. Parse ANSI output into a list of lines (same approach as _run_captured_dialog)
    raw_segments = ANSI(ansi_text).__pt_formatted_text__()
    all_lines: list[list] = []
    current_line: list = []
    for style, text in raw_segments:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                all_lines.append(current_line)
                current_line = []
            if part:
                current_line.append((style, part))
    if current_line:
        all_lines.append(current_line)

    total_lines = len(all_lines)
    viewport_start = [0]

    def content():
        term_h = shutil.get_terminal_size((80, 24)).lines
        visible_n = max(1, term_h - 2)
        start = viewport_start[0]
        end = min(total_lines, start + visible_n)

        out: list = []
        for line in all_lines[start:end]:
            out.extend(line)
            out.append(("", "\n"))

        remaining = total_lines - end
        if remaining > 0:
            out.append(("fg:#f9e2af",
                        f"  ▼ {remaining} more line{'s' if remaining > 1 else ''} (↓ / PgDn to scroll)\n"))
        elif start > 0:
            out.append(("fg:#555577", "  ─ end of content ─\n"))
        return out

    # 3. Key bindings
    kb = KeyBindings()

    @kb.add('escape')
    @kb.add('q')
    @kb.add('enter')
    @kb.add('c-c')
    def _close(e):
        e.app.exit()

    def _scroll(delta: int, app):
        vp = viewport_start[0] + delta
        viewport_start[0] = max(0, min(total_lines - 1, vp))
        app.invalidate()

    @kb.add('up')
    @kb.add('k')
    def _up(e): _scroll(-1, e.app)

    @kb.add('down')
    @kb.add('j')
    def _dn(e): _scroll(1, e.app)

    @kb.add('pageup')
    def _pgup(e): _scroll(-15, e.app)

    @kb.add('pagedown')
    def _pgdn(e): _scroll(15, e.app)

    @kb.add('<scroll-up>')
    def _mup(e): _scroll(-3, e.app)

    @kb.add('<scroll-down>')
    def _mdn(e): _scroll(3, e.app)

    dialog_app = Application(
        layout=Layout(Window(FormattedTextControl(content), wrap_lines=False)),
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({'dim': '#555577', '': 'bg:#0d0d16 fg:#cdd6f4'}),
        mouse_support=True,
    )
    dialog_app.run()


def _run_captured_dialog(title: str, print_fn):
    """
    Full-screen scrollable viewer for Rich-captured content.
    Uses a manual viewport (list of parsed ANSI lines) so that
    UP/DOWN/PageUp/PageDown/mouse-wheel all reliably scroll the view.
    """
    import shutil
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style as PTStyle
    from prompt_toolkit.formatted_text import ANSI
    from rich.console import Console

    width = min(80, get_console_width())
    capture_console = Console(
        theme=custom_theme,
        highlight=False,
        force_terminal=True,
        color_system="truecolor",
        width=width,
    )

    with capture_console.capture() as cap:
        capture_console.print()
        capture_console.print("=" * width, style="dim")
        capture_console.print(f" {title.upper()} ", style="bold #42bcf5", justify="center")
        capture_console.print("=" * width, style="dim")
        print_fn(capture_console)
        capture_console.print("-" * width, style="dim")
        capture_console.print(
            " ↑/↓ scroll · PageUp/PageDown jump · ESC/Q close ",
            style="italic dim", justify="center",
        )
        capture_console.print("-" * width, style="dim")
        capture_console.print()

    ansi_text = cap.get()

    # ── Parse ANSI output into a list of lines ────────────────────────────────
    # prompt_toolkit's ANSI parser produces absolute styles per segment, so
    # splitting by \n is safe — no colour bleed across lines.
    raw_segments = ANSI(ansi_text).__pt_formatted_text__()
    all_lines: list[list] = []
    current_line: list = []
    for style, text in raw_segments:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                all_lines.append(current_line)
                current_line = []
            if part:
                current_line.append((style, part))
    if current_line:
        all_lines.append(current_line)

    total_lines = len(all_lines)
    viewport_start = [0]

    def content():
        term_h = shutil.get_terminal_size((80, 24)).lines
        visible_n = max(1, term_h - 2)          # leave 2 rows for status bar
        start = viewport_start[0]
        end   = min(total_lines, start + visible_n)

        out: list = []
        for line in all_lines[start:end]:
            out.extend(line)
            out.append(("", "\n"))

        # Scroll indicator at the bottom
        remaining = total_lines - end
        if remaining > 0:
            out.append(("fg:#f9e2af",
                        f"  ▼ {remaining} more line{'s' if remaining > 1 else ''} (↓ / PgDn to scroll)\n"))
        elif start > 0:
            out.append(("fg:#555577", "  ─ end of content ─\n"))
        return out

    kb = KeyBindings()

    @kb.add("escape")
    @kb.add("q")
    @kb.add("enter")
    @kb.add("c-c")
    def _close(e):
        e.app.exit()

    def _scroll(delta: int, app):
        vp = viewport_start[0] + delta
        viewport_start[0] = max(0, min(total_lines - 1, vp))
        app.invalidate()

    @kb.add("up")
    def _up(e): _scroll(-1, e.app)

    @kb.add("down")
    def _dn(e): _scroll(1, e.app)

    @kb.add("pageup")
    def _pgup(e): _scroll(-15, e.app)

    @kb.add("pagedown")
    def _pgdn(e): _scroll(15, e.app)

    @kb.add("<scroll-up>")
    def _mup(e): _scroll(-3, e.app)

    @kb.add("<scroll-down>")
    def _mdn(e): _scroll(3, e.app)

    dialog_app = Application(
        layout=Layout(Window(FormattedTextControl(content), wrap_lines=False)),
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({"dim": "#555577", "": "bg:#0d0d16 fg:#cdd6f4"}),
        mouse_support=True,
    )
    dialog_app.run()


# ─── Global App State ─────────────────────────────────────────────────────────
from utim_cli.state import STATE

_tip_idx = 0
_tip_request_count = 0   # increments every request; tip advances every 3
_TIPS = []

def _next_tip():
    """Advance the tip index every 3 model requests and return the current tip."""
    global _tip_idx, _tip_request_count
    _tip_request_count += 1
    if not _TIPS:
        return ""
    # Rotate to the next tip every 3 requests
    if _tip_request_count % 3 == 0:
        _tip_idx = (_tip_idx + 1) % len(_TIPS)
    return _TIPS[_tip_idx]


# ─── Slash Commands ───────────────────────────────────────────────────────────
from utim_cli.wheel import WHEEL_COMMANDS, is_wheel_command, execute_wheel_cli_flow

COMMANDS = {
    "about":    "Show version info",
    "clear":    "Clear conversation history",
    "doctor":   "Run system, environment, and MCP connectivity diagnostics",
    "help":     "Show this help panel",
    "hint":     "Inject secret guidance hint for the next turn prompt",
    "login":    "Sign in to your UTIM account",
    "logout":   "Sign out of your account",
    "mcp":      "Manage, install, and connect Model Context Protocol (MCP) servers",
    "model":    "Select or add a model from any provider",
    "modelsettings": "Change settings for the selected model (temperature, max output, reasoning effort)",
    "new":      "Start a new chat session (clears active screen)",
    "quit":     "Exit the CLI",
    "quota":    "Choose credit quota to use ('regular' or 'bonus')",
    "quotashare": "Share regular plan credits with your referred users",
    "redeem":   "Redeem a shared credit quota code",
    "redo":     "Redo the last undone action",
    "report":   "Generate a redacted support zip bundle under .utim_tmp/",
    "chatrestore": "Toggle active session state auto-restoration on startup",
    "sslverify": "Toggle SSL certificate validation (useful behind decrypting proxies)",
    "resume":   "Manage/Load previous conversations",
    "rewind":   "Undo last action and revert code",
    "share":    "Share chat and zip package of the workspace",
    "miniagents": "Create, view, and delete custom executable miniagent tools",
    "marketplace": "Browse, download, install, and publish custom skills, tools, and miniagents",
    "skills":    "Activate, deactivate, create, or delete custom AI skills",
    "tools":    "Select, enable, or disable built-in and MCP tools",
    "usage":    "Check quota usage and refill limits",
    "rate":     "Rate the last response and submit feedback",
    "feedbacks": "View user feedbacks dashboard (Admin only)",
    **WHEEL_COMMANDS
}

class SlashCommandCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith('/'):
            if text.count(' ') == 0:
                word = text[1:]
                from utim_cli.config import config
                user_uid = config.get("firebase_uid") or config.get("uid")
                ALLOWED_FIREBASE_IDS = {"JL763NoYOlRHV5WSkL9ySpz5gkI3", "HADaFqH9p0brRlMAs5mtEbwuBzk1"}

                visible_commands = dict(COMMANDS)
                if user_uid not in ALLOWED_FIREBASE_IDS:
                    visible_commands.pop("feedbacks", None)

                # If word matches an exact full command name, return 0 completions to close the dropdown menu
                if word.lower() in visible_commands:
                    return

                # Match the exact width and spacing from the screenshot
                max_cmd_len = max(len(c) for c in visible_commands)
                for cmd, desc in visible_commands.items():
                    if not word or cmd.startswith(word):
                        # Pad the command so descriptions align
                        display_text = cmd.ljust(max_cmd_len + 4)
                        yield Completion(
                            cmd, 
                            start_position=-len(word),
                            display=display_text, 
                            display_meta=desc,
                        )

# ─── @-Mention Completer (miniagents, skills) ───────────────────────────────

VALID_AT_TAGS = {"@miniagents", "@miniagent", "@skills", "@skill"}

_AT_DROPDOWN_OPTIONS = [
    {"cmd": "miniagents", "display": "miniagents", "meta": "Create custom executable miniagent tools with AI guidance"},
    {"cmd": "skills", "display": "skills", "meta": "Create custom skill guidelines with AI guidance"},
]


class AtMentionCompleter(Completer):
    """Autocomplete @-mentions showing 'subagents', 'miniagents', and 'skills'."""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()
        if not stripped.startswith('@'):
            return
        if ' ' in stripped:
            return  # Only complete the first token
        word = stripped[1:].lower()  # text typed after '@'

        for opt in _AT_DROPDOWN_OPTIONS:
            if not word or opt["cmd"].startswith(word):
                display_text = opt["display"].ljust(14)
                yield Completion(
                    opt["cmd"],
                    start_position=-len(word),
                    display=display_text,
                    display_meta=opt["meta"],
                )


class HashFileCompleter(Completer):
    """Autocomplete workspace files and folders when user types '#'."""
    _cache = {'files': [], 'ts': 0.0}

    def _get_workspace_files(self):
        import time, os
        now = time.monotonic()
        if now - self._cache['ts'] < 2.0:
            return self._cache['files']

        ignored_dirs = {
            "node_modules", ".git", "out", "dist", "build", ".next",
            ".utim", ".utim_tmp", "__pycache__", ".venv", "venv",
            ".idea", ".vscode", "coverage", ".turbo"
        }
        root = os.getcwd()
        file_list = []
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in ignored_dirs and not d.startswith('.')]
                rel_dir = os.path.relpath(dirpath, root)

                # Add directories to completion list
                for d in dirnames:
                    rel_d = d if rel_dir == "." else os.path.join(rel_dir, d).replace("\\", "/")
                    file_list.append(rel_d + "/")

                for f in filenames:
                    if f.startswith('.'):
                        continue
                    rel_path = f if rel_dir == "." else os.path.join(rel_dir, f).replace("\\", "/")
                    file_list.append(rel_path)
                    if len(file_list) >= 500:
                        break
                if len(file_list) >= 500:
                    break
        except Exception:
            pass

        self._cache['files'] = file_list
        self._cache['ts'] = now
        return file_list

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        import re
        match = re.search(r'#([^\s#]*)$', text)
        if not match:
            return

        query = match.group(1).lower()
        files = self._get_workspace_files()

        for f in files:
            f_lower = f.lower()
            if not query or query in f_lower:
                replacement = f'"{f}"' if ' ' in f else f
                display_text = f if len(f) <= 45 else f[:20] + "..." + f[-22:]
                yield Completion(
                    replacement,
                    start_position=-(len(query) + 1),  # Replaces the leading '#' character
                    display=display_text,
                    display_meta="Folder" if f.endswith("/") else "File",
                )


class CombinedCompleter(Completer):
    """Delegates to SlashCommandCompleter for '/', AtMentionCompleter for '@', and HashFileCompleter for '#'."""
    def __init__(self):
        self._slash = SlashCommandCompleter()
        self._at = AtMentionCompleter()
        self._hash = HashFileCompleter()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()
        if stripped.startswith('/'):
            yield from self._slash.get_completions(document, complete_event)
        elif stripped.startswith('@'):
            yield from self._at.get_completions(document, complete_event)
        elif '#' in text:
            yield from self._hash.get_completions(document, complete_event)


# ─── Prompt-Toolkit Style ─────────────────────────────────────────────────────
PT_STYLE = PTStyle.from_dict({
    # Input area
    'input-field':        'fg:#cdd6f4',
    'input-prompt':       'fg:#cdd6f4 bold',
    'image-path':         'fg:#a6e3a1',
    'at-tag':             'fg:#89b4fa bold',      # @subagent tag — blue
    'hash-file':          'fg:#89dceb bold',      # #file tag — cyan
    'placeholder':        'fg:#45475a italic',

    # Status bar
    'status-bar':         '',
    'sb-auto':            'fg:#FFE066 bold',
    'sb-manual':          'fg:#66FFEE bold',
    'sb-working':         'fg:#C678DD bold italic',
    'sb-dim':             'fg:#585b70',
    'sb-tip':             'fg:#585b70',

    # Footer
    'footer':             '',
    'ft-label':           'fg:#585b70',
    'ft-cwd':             'fg:#cdd6f4',
    'ft-nosandbox':       'fg:#ff5555 bold',
    'ft-sandbox':         'fg:#a6e3a1 bold',

    # Completion menu - Matching screenshot colors exactly
    'completion-menu':                    'bg:#181825 fg:#cdd6f4',
    'completion-menu.completion':         'bg:#181825 fg:#cdd6f4',
    'completion-menu.completion.current': 'bg:#a6e3a1 fg:#1e1e2e bold',
    'completion-menu.meta.completion':    'bg:#181825 fg:#9399b2',
    'completion-menu.meta.completion.current': 'bg:#a6e3a1 fg:#1e1e2e',
    'scrollbar.background':               'bg:#181825',
    'scrollbar.button':                   'bg:#313244',

    # Live shell panel
    'shell-panel':        'bg:#0d0e18 fg:#cdd6f4',
    'shell-header':       'fg:#f9e2af bold',
    'shell-header-dim':   'fg:#585b70',
    'shell-focused-hint': 'fg:#a6e3a1 bold',
})

# ─── UI Helpers ───────────────────────────────────────────────────────────────
# Smooth 12-frame arc spinner — fluid at 12 fps
from utim_cli.constants import _IS_LEGACY_WIN
import sys
_SPINNER_CHARS = ['|', '/', '-', '\\'] if (_IS_LEGACY_WIN or getattr(sys.stdout, 'encoding', '').lower() not in ('utf-8', 'utf8', 'cp65001')) else ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧']
def _spinner_frame():
    """Return a rotating spinner character."""
    idx = int(time.time() * 10) % len(_SPINNER_CHARS)
    return _SPINNER_CHARS[idx]

def _get_chat_thinking():
    import time
    if not STATE.get("busy"):
        return []
    out = []
    queue = STATE.get("queue", [])
    if queue:
        out.append(('class:dim', 'Queued (press \u2191 to edit):\n'))
        for item in queue:
            lines = item.splitlines()
            first_line = lines[0] if lines else ""
            if len(lines) > 1:
                first_line += " \u2026"
            if len(first_line) > 80:
                first_line = first_line[:77] + "..."
            out.append(('class:dim', f'  {first_line}\n'))
        out.append(('', '\n'))
        
    elapsed = ""
    start_time = STATE.get("busy_start")
    if start_time:
        diff = int(time.time() - start_time)
        elapsed = f", {diff}s"

    topic = STATE.get("thinking_topic") or "Thinking..."
    out.append(('class:sb-working', f'  {_spinner_frame()} {topic} (esc to cancel{elapsed})'))
    out.append(('', '\n'))
    if _TIPS:
        current_tip = _TIPS[_tip_idx % len(_TIPS)]
        out.append(('class:dim', f'  \u2514 {current_tip}'))
    return out

def _get_status_bar_left():
    mode = STATE["mode"]

    # ── Shell-focused mode overrides everything else ───────────────────────
    if _SHELL["active"] and _SHELL["focused"]:
        l_text = " ● FOCUSED "
        l_hint = " Ctrl+C to kill   Shift+Tab to return to agent "
        left   = [('class:shell-focused-hint', l_text), ('class:sb-dim', l_hint)]
    elif _SHELL["active"]:
        l_text = " ! Shell running"
        l_hint = "  Tab to focus "
        left   = [('class:sb-working', l_text), ('class:sb-dim', l_hint)]
    elif STATE.get("focus_mode") and STATE.get("focused_process"):
        l_text = f' FOCUSED on process #{STATE["focused_process"]}'
        l_hint = '  Shift+Tab to unfocus '
        left   = [('class:sb-manual', l_text), ('class:sb-dim', l_hint)]
    elif mode == "auto-accept edits":
        left   = []
    else:
        left   = []
    return left

def _get_status_bar_right():
    return []

def _get_footer_line1_left():
    return []


def _get_footer_line1_right():
    return []

def _get_footer_line2_left():
    cwd  = os.getcwd()
    home = os.path.expanduser("~")
    l2 = ("~" + cwd[len(home):]) if cwd.startswith(home) else cwd
    return [('class:ft-cwd', ' ' + l2)]
def _get_footer_line2_right():
    return []



def _clear_terminal_screen():
    """Clear the terminal screen in a robust, cross-platform way."""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

# ─── Startup Banner ───────────────────────────────────────────────────────────
BANNER_BIG = """
 ██╗   ██╗████████╗██╗███╗   ███╗     █████╗ ██╗
 ██║   ██║╚══██╔══╝██║████╗ ████║    ██╔══██╗██║
 ██║   ██║   ██║   ██║██╔████╔██║    ███████║██║
 ██║   ██║   ██║   ██║██║╚██╔╝██║    ██╔══██║██║
 ╚██████╔╝   ██║   ██║██║ ╚═╝ ██║    ██║  ██║██║
  ╚═════╝    ╚═╝   ╚═╝╚═╝     ╚═╝    ╚═╝  ╚═╝╚═╝"""

def _print_animated_banner(animated: bool = True):
    """Print a large UTIM AI banner with a character-by-character typing effect or static."""
    color = "#42bcf5"
    
    console.print()
    if animated:
        # Type out the big logo character by character
        for char in BANNER_BIG:
            if char == '\n':
                sys.stdout.write('\n')
            else:
                # Use rich to print the colored character
                console.print(f"[bold {color}]{char}[/bold {color}]", end="")
            
            sys.stdout.flush()
            # Speed up for spaces to make it feel more like typing
            time.sleep(0.002 if char == " " else 0.005)
        console.print()
    else:
        console.print(f"[bold {color}]{BANNER_BIG}[/bold {color}]")
            
    console.print(f" [bold white]U Think I Make[/bold white] [bold #cba6f7]v2.2.1[/bold #cba6f7]")
    user_email = config.email
    is_logged_in = bool(config.token and user_email and user_email.upper() != "GUEST")
    user_type = "Guest Mode" if not is_logged_in else "UTIM Community"
    api_key = config.get("api_key")
    PLAN_NAME_MAP = {
        "free": "Free",
        "hobby": "Hobbyist Node",
        "pro": "Starter Node",
        "max": "Professional Core",
        "ultimate": "MAX Node"
    }
    if is_logged_in and api_key:
        cached_plan = config.get("user_plan", "free")
        user_type = f"UTIM {PLAN_NAME_MAP.get(str(cached_plan).lower().strip(), str(cached_plan).title())}"
        
        # Fire a quick request to check and refresh plan from server
        try:
            from utim_cli.auth import SERVER_URL
            import requests
            resp = requests.get(
                f"{SERVER_URL}/api/user-plan",
                headers={"X-API-Key": api_key},
                timeout=5.0,
            )
            if resp.ok:
                body = resp.json()
                plan_name = body.get("plan", "free")
                config.set("user_plan", plan_name)
                if "firebase_uid" in body:
                    config.set("firebase_uid", body["firebase_uid"])
                user_type = f"UTIM {PLAN_NAME_MAP.get(plan_name.lower().strip(), plan_name.title())}"
        except Exception:
            pass
    console.print(f" [dim]{user_email}  •  {user_type}[/dim]")
    console.print()



NOTIFICATION = (
    "[bold #FFE066]We're building the next generation of UTIM CLI.[/bold #FFE066]\n"
    "  [dim]What's New:[/dim]  Agent memory, vision tools, multi-model routing, & Model Context Protocol (MCP).\n"
    "  [dim]What's Next:[/dim] Next we will be adding tools marketplace"
)

def _flush_stdin_buffer():
    import sys
    if sys.platform == "win32":
        try:
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
        except Exception:
            pass
    else:
        try:
            import termios
            if sys.stdin.isatty():
                termios.tcflush(sys.stdin, termios.TCIFLUSH)
        except Exception:
            pass

# ─── Interactive list dialog (used by /model, /resume, /rewind) ───────────────

def _set_inline_edit(field: str, label: str, default: str = ""):
    """Signal the running list dialog to enter inline edit mode.
    
    This is called by on_enter callbacks. It sets state on the running
    Application so that content() renders an edit buffer and key bindings
    capture keystrokes into it.
    """
    from prompt_toolkit.application import get_app
    try:
        app = get_app()
        app._edit_mode = True
        app._edit_buf = default
        app._edit_label = label
        app._edit_field = field
        app.invalidate()
    except Exception:
        pass


def _parse_rich_title_to_pt(title_str: str) -> list:
    """Parse title strings containing rich tags like [dim]...[/dim] into prompt_toolkit tuples."""
    import re
    if not title_str:
        return [('', '')]
    
    parts = []
    tokens = re.split(r'(\[dim\].*?\[/dim\]|\[bold\].*?\[/bold\])', title_str)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith('[dim]') and tok.endswith('[/dim]'):
            inner = tok[5:-6]
            parts.append(('fg:#7f849c', inner))
        elif tok.startswith('[bold]') and tok.endswith('[/bold]'):
            inner = tok[6:-7]
            parts.append(('bold fg:#89b4fa', inner))
        else:
            parts.append(('bold fg:#89b4fa', tok))
    return [('bold fg:#89b4fa', '\n  '), *parts, ('', '\n')]


def _sanitize_style_to_bw(style: str, selected: bool) -> str:
    """
    Apply clean modern dark theme styling to dialog elements.
    Preserves rich accent colors (cyan, green, yellow, coral red, lavender) while adding
    soft background highlights (#313244) for selected items.
    """
    if not style:
        return 'bg:#313244 fg:#cdd6f4' if selected else 'fg:#cdd6f4'

    style_lower = style.lower().strip()

    if 'frame.border' in style_lower:
        return 'fg:#585b70'
    if 'search-field' in style_lower:
        return 'bg:#1e1e2e fg:#cdd6f4'

    if selected:
        if 'bg:' in style_lower:
            return style
        return f"{style} bg:#313244"

    return style


def _run_list_dialog(rows, render_row_fn, title="", legend="", extra_keys=None, is_selectable_fn=None, on_enter=None):
    """
    Full-screen interactive list. Returns (action_str, selected_index) or
    (None, None) if the user quits.
    rows        — list of any objects
    render_row_fn(idx, row, selected) — returns list of (style, text) tuples
    extra_keys  — dict {key_str: action_str} for additional bindings
    is_selectable_fn — optional function(row) -> bool to skip non-interactive rows
    on_enter    — optional async function(idx, row, app) -> bool. Called when Enter
                  is pressed. Return True to stay in dialog, False/None to exit.
    """
    if not rows:
        return None, None

    # Flush any lingering key events (e.g. Enter bleed from previous dialog)
    _flush_stdin_buffer()

    N = len(rows)
    start_idx = 0
    if is_selectable_fn:
        for i in range(N):
            if is_selectable_fn(rows[i]):
                start_idx = i
                break

    sel   = [start_idx]
    act   = [None]   # filled on selection

    # ── Inline edit state (stored on app object after it's created) ────────
    # Set by on_enter callbacks. content() reads via get_app().

    # Pre-calculate render heights for each row to handle dynamic terminal height
    row_heights = []
    for i, row in enumerate(rows):
        try:
            rendered = render_row_fn(i, row, False)
            newlines = sum(text.count('\n') for _, text in rendered)
            row_heights.append(max(1, newlines))
        except Exception:
            row_heights.append(2)  # default fallback

    viewport_start = [0]

    def content():
        import shutil
        term_h = shutil.get_terminal_size().lines

        N = len(rows)
        while len(row_heights) < N:
            i = len(row_heights)
            try:
                rendered = render_row_fn(i, rows[i], False)
                newlines = sum(text.count('\n') for _, text in rendered)
                row_heights.append(max(1, newlines))
            except Exception:
                row_heights.append(2)

        # Calculate available height for rendering list rows
        # Budget 7 lines for headers, spacing, legend, and footer spacing
        available_height = max(5, term_h - 7)
        
        # Check if we need scrolling indicators and adjust available height
        # If there are items above, we'll display a 2-line indicator
        if viewport_start[0] > 0:
            available_height -= 2
            
        # If the remaining items don't fit, we'll display a 1-line indicator at the bottom
        total_remaining_height = sum(row_heights[viewport_start[0]:])
        if total_remaining_height > available_height:
            available_height -= 1

        # Keep available_height positive
        available_height = max(1, available_height)

        # Ensure viewport_start is within valid range [0, N-1]
        viewport_start[0] = max(0, min(N - 1, viewport_start[0]))

        # Adjust viewport_start only when sel[0] is out of bounds of current viewport
        if sel[0] < viewport_start[0]:
            viewport_start[0] = sel[0]
        else:
            current_height = 0
            for idx in range(viewport_start[0], sel[0] + 1):
                current_height += row_heights[idx]
            while current_height > available_height and viewport_start[0] < sel[0]:
                current_height -= row_heights[viewport_start[0]]
                viewport_start[0] += 1

        out: list = []
        out.append(('bold white', f'\n  {title}\n'))
        out.append(('class:dim',    f'  {legend}\n\n'))

        # Show indicator for items above the viewport
        if viewport_start[0] > 0:
            out.append(('class:dim', f'    ▲ ... ({viewport_start[0]} more item{"s" if viewport_start[0] > 1 else ""} above) ... ▲\n\n'))

        # Render rows that fit in available height
        rendered_height = 0
        end_idx = viewport_start[0]
        while end_idx < N and rendered_height + row_heights[end_idx] <= available_height:
            rendered_height += row_heights[end_idx]
            end_idx += 1

        # Make sure we render at least the selected row if viewport calculations are tight
        if end_idx <= sel[0]:
            end_idx = sel[0] + 1

        from prompt_toolkit.mouse_events import MouseEventType
        from prompt_toolkit.application import get_app

        def _make_click_handler(row_idx):
            def _on_click(mouse_event):
                if mouse_event.event_type == MouseEventType.SCROLL_UP:
                    viewport_start[0] = max(0, viewport_start[0] - 1)
                    # Move selection up if it goes out of view
                    if sel[0] > viewport_start[0] + 15:
                        sel[0] = viewport_start[0]
                    try:
                        get_app().invalidate()
                    except Exception:
                        pass
                    return
                if mouse_event.event_type == MouseEventType.SCROLL_DOWN:
                    viewport_start[0] = min(N - 1, viewport_start[0] + 1)
                    # Move selection down if it goes above view
                    if sel[0] < viewport_start[0]:
                        sel[0] = viewport_start[0]
                        if is_selectable_fn:
                            while sel[0] < N - 1 and not is_selectable_fn(rows[sel[0]]):
                                sel[0] += 1
                    try:
                        get_app().invalidate()
                    except Exception:
                        pass
                    return
                if is_selectable_fn and not is_selectable_fn(rows[row_idx]):
                    return
                if mouse_event.event_type in (MouseEventType.MOUSE_UP, MouseEventType.MOUSE_DOWN):
                    if sel[0] == row_idx and mouse_event.event_type == MouseEventType.MOUSE_UP:
                        act[0] = 'select'
                        try:
                            get_app().exit()
                        except Exception:
                            pass
                    else:
                        sel[0] = row_idx
                        try:
                            get_app().invalidate()
                        except Exception:
                            pass
            return _on_click

        for i in range(viewport_start[0], end_idx):
            # Check if we're inline-editing this row
            try:
                _app = get_app()
                _editing = getattr(_app, '_edit_mode', False)
                _buf = getattr(_app, '_edit_buf', '')
                _label = getattr(_app, '_edit_label', '')
            except Exception:
                _editing = False
                _buf = ''
                _label = ''

            if _editing and i == sel[0]:
                # Replace the rendered row with the edit buffer
                display_text = f"{_label}{_buf}█"  # █ = cursor
                processed_row = [('', f"  {display_text}\n")]
            else:
                rendered_row = render_row_fn(i, rows[i], i == sel[0])
                click_fn = _make_click_handler(i)
                processed_row = []
                for item in rendered_row:
                    style = item[0]
                    text = item[1]
                    if text.startswith("  ➔ "):
                        text = text.replace("  ➔ ", f"  {ARROW_SYMBOL} ")
                    elif text.startswith("      "):
                        text = (" " * (5 + len(ARROW_SYMBOL))) + text[6:]
                    elif text.startswith("    "):
                        text = (" " * (3 + len(ARROW_SYMBOL))) + text[4:]
                    elif "➔" in text:
                        text = text.replace("➔", ARROW_SYMBOL)
                    sanitized_style = _sanitize_style_to_bw(style, i == sel[0])
                    processed_row.append((sanitized_style, text, click_fn))
            out.extend(processed_row)

        # Show indicator for items below the viewport
        remaining = N - end_idx
        if remaining > 0:
            out.append(('class:dim', f'    ▼ ... ({remaining} more item{"s" if remaining > 1 else ""} below) ... ▼\n'))

        out.append(('', '\n'))
        return out

    kb2 = KeyBindings()

    @kb2.add('up')
    @kb2.add('k')
    def _up(e):
        new_sel = (sel[0] - 1) % N
        if is_selectable_fn:
            steps = 0
            while not is_selectable_fn(rows[new_sel]) and steps < N:
                new_sel = (new_sel - 1) % N
                steps += 1
        sel[0] = new_sel
        e.app.invalidate()

    @kb2.add('down')
    @kb2.add('j')
    def _dn(e):
        new_sel = (sel[0] + 1) % N
        if is_selectable_fn:
            steps = 0
            while not is_selectable_fn(rows[new_sel]) and steps < N:
                new_sel = (new_sel + 1) % N
                steps += 1
        sel[0] = new_sel
        e.app.invalidate()

    @kb2.add('g')
    def _first(e):
        new_sel = 0
        if is_selectable_fn:
            for i in range(N):
                if is_selectable_fn(rows[i]):
                    new_sel = i
                    break
        sel[0] = new_sel
        e.app.invalidate()

    @kb2.add('G')
    def _last(e):
        new_sel = N - 1
        if is_selectable_fn:
            for i in range(N - 1, -1, -1):
                if is_selectable_fn(rows[i]):
                    new_sel = i
                    break
        sel[0] = new_sel
        e.app.invalidate()

    @kb2.add('enter')
    async def _enter(e):
        _app = e.app
        if getattr(_app, '_edit_mode', False):
            # Accept inline edit: call on_enter with the buffer value
            buf_val = getattr(_app, '_edit_buf', '')
            if on_enter is not None:
                try:
                    stay = await on_enter(sel[0], rows[sel[0]], _app, buf_val)
                    if stay:
                        _app._edit_mode = False
                        _app._edit_buf = ''
                        _app._edit_field = None
                        _app.invalidate()
                        return
                except Exception:
                    pass
            _app._edit_mode = False
            _app._edit_buf = ''
            _app._edit_field = None
            _app.invalidate()
            return
        if is_selectable_fn and not is_selectable_fn(rows[sel[0]]):
            return
        if on_enter is not None:
            try:
                stay = await on_enter(sel[0], rows[sel[0]], _app)
                if stay:
                    _app.invalidate()
                    return
            except Exception:
                pass
        act[0] = 'select'
        try:
            _app.exit()
        except Exception:
            pass

    @kb2.add('escape')
    @kb2.add('q')
    @kb2.add('c-c')
    def _quit(e):
        _app = e.app
        if getattr(_app, '_edit_mode', False):
            # Cancel inline edit
            _app._edit_mode = False
            _app._edit_buf = ''
            _app._edit_field = None
            _app.invalidate()
            return
        try:
            _app.exit()
        except Exception:
            pass

    # ── Inline editing keys ────────────────────────────────────────────────
    @kb2.add('backspace')
    def _bs(e):
        _app = e.app
        if getattr(_app, '_edit_mode', False):
            if _app._edit_buf:
                _app._edit_buf = _app._edit_buf[:-1]
                _app.invalidate()
            return

    # Catch all printable characters for inline editing
    import string as _string
    for _ch in _string.printable:
        if _ch in ('\n', '\r', '\t', '\x0b', '\x0c'):
            continue
        try:
            @kb2.add(_ch)
            def _char_handler(e, ch=_ch):
                _app = e.app
                if getattr(_app, '_edit_mode', False):
                    _app._edit_buf += ch
                    _app.invalidate()
                    return
        except Exception:
            pass

    # Scroll viewport directly (without moving selection)
    @kb2.add('pageup')
    def _pg_up(e):
        viewport_start[0] = max(0, viewport_start[0] - 5)
        e.app.invalidate()

    @kb2.add('pagedown')
    def _pg_dn(e):
        viewport_start[0] = min(N - 1, viewport_start[0] + 5)
        e.app.invalidate()

    @kb2.add('<scroll-up>')
    def _mscroll_up(e):
        viewport_start[0] = max(0, viewport_start[0] - 1)
        if sel[0] > viewport_start[0] + 15:
            sel[0] = viewport_start[0]
        e.app.invalidate()

    @kb2.add('<scroll-down>')
    def _mscroll_dn(e):
        viewport_start[0] = min(N - 1, viewport_start[0] + 1)
        if sel[0] < viewport_start[0]:
            sel[0] = viewport_start[0]
            if is_selectable_fn:
                while sel[0] < N - 1 and not is_selectable_fn(rows[sel[0]]):
                    sel[0] += 1
        e.app.invalidate()

    if extra_keys:
        for key, action in extra_keys.items():
            def _make_handler(a):
                def _h(e):
                    act[0] = a
                    try:
                        e.app.exit()
                    except Exception:
                        pass
                return _h
            kb2.add(key)(_make_handler(action))

    dialog_app = Application(
        layout=Layout(Window(
            FormattedTextControl(content),
            wrap_lines=False,
        )),
        key_bindings=kb2,
        full_screen=True,
        style=PTStyle.from_dict({'dim': '#888888', '': 'bg:#000000 fg:#ffffff'}),
        mouse_support=True,
    )
    # Initialize inline edit state on the app
    dialog_app._edit_mode = False
    dialog_app._edit_buf = ""
    dialog_app._edit_label = ""
    dialog_app._edit_field = None
    dialog_app.run()
    _flush_stdin_buffer()
    return act[0], sel[0]


# ─── Searchable List Dialog for MCP ───────────────────────────────────────────

def _run_search_list_dialog(
    rows,
    render_row_fn,
    title="",
    legend="",
    extra_keys=None,
    search_prompt=" Search: ",
    search_title="Filter List",
    list_title="Items",
    initial_index=0
):
    """
    Searchable interactive list dialog with generic support for extra_keys.
    Allows real-time search of key fields in rows.
    """
    if not rows:
        return None, None

    _flush_stdin_buffer()

    sel = [initial_index]
    act = [None]
    viewport_start = [0]
    filtered_rows = []
    N_filtered = [0]

    # Pre-calculate row heights
    row_heights = []
    for i, row in enumerate(rows):
        try:
            rendered = render_row_fn(i, row, False)
            newlines = sum(text.count('\n') for _, text in rendered)
            row_heights.append(max(1, newlines))
        except Exception:
            row_heights.append(2)

    def update_filtered_rows(query, reset_selection=True):
        nonlocal filtered_rows
        q = query.strip().lower()
        if not q:
            filtered_rows = list(enumerate(rows))
        else:
            # Replace hyphens, underscores, and slashes with spaces to handle separator mismatches
            q_norm = q.replace('-', ' ').replace('_', ' ').replace('/', ' ')
            q_words = [w for w in q_norm.split() if w]
            
            filtered_rows = []
            for idx, r in enumerate(rows):
                # Search across common fields
                model_id = str(r.get("model_id", "")).lower()
                name = str(r.get("name", "")).lower()
                desc = str(r.get("desc", "")).lower()
                key = str(r.get("key", "")).lower()
                tags = " ".join(str(t) for t in r.get("tags", [])).lower()
                
                # Combine search target text and normalize it
                search_text = f"{model_id} {name} {desc} {key} {tags}"
                search_text_norm = search_text.replace('-', ' ').replace('_', ' ').replace('/', ' ')
                
                # Verify that ALL query words exist in the normalized target text
                if all(word in search_text_norm for word in q_words):
                    filtered_rows.append((idx, r))
        N_filtered[0] = len(filtered_rows)
        if reset_selection:
            sel[0] = 0
            viewport_start[0] = 0

    def content():
        import shutil
        term_h = shutil.get_terminal_size().lines
        available_height = max(5, term_h - 10)
        
        if N_filtered[0] == 0:
            return [
                ('', '\n'),
                ('bold #f38ba8', '    No matching items found.\n')
            ]

        matching_heights = [row_heights[orig_idx] for orig_idx, _ in filtered_rows]

        if sel[0] < viewport_start[0]:
            viewport_start[0] = sel[0]
        else:
            current_height = 0
            for idx in range(viewport_start[0], sel[0] + 1):
                current_height += matching_heights[idx]
            while current_height > available_height and viewport_start[0] < sel[0]:
                current_height -= matching_heights[viewport_start[0]]
                viewport_start[0] += 1

        out = []
        if viewport_start[0] > 0:
            out.append(('class:dim', f'    ▲ ... ({viewport_start[0]} more above) ... ▲\n\n'))
            available_height -= 2

        rendered_height = 0
        end_idx = viewport_start[0]
        while end_idx < N_filtered[0] and rendered_height + matching_heights[end_idx] <= available_height:
            rendered_height += matching_heights[end_idx]
            end_idx += 1

        if end_idx <= sel[0]:
            end_idx = sel[0] + 1

        for i in range(viewport_start[0], end_idx):
            orig_idx, row = filtered_rows[i]
            rendered_row = render_row_fn(orig_idx, row, i == sel[0])
            processed_row = []
            for item in rendered_row:
                style = item[0]
                text = item[1]
                click_fn = item[2] if len(item) > 2 else None
                sanitized_style = _sanitize_style_to_bw(style, i == sel[0])
                if click_fn:
                    processed_row.append((sanitized_style, text, click_fn))
                else:
                    processed_row.append((sanitized_style, text))
            out.extend(processed_row)

        remaining = N_filtered[0] - end_idx
        if remaining > 0:
            out.append(('class:dim', f'\n    ▼ ... ({remaining} more below) ... ▼\n'))

        return out

    title_window = Window(FormattedTextControl(_parse_rich_title_to_pt(title)), height=2)

    search_field = TextArea(
        multiline=False,
        prompt=search_prompt,
        style="class:search-field",
    )
    search_field.buffer.on_text_changed += lambda buf: update_filtered_rows(buf.text)
    search_frame = Frame(search_field, title=search_title)

    list_control = FormattedTextControl(content, focusable=True)
    list_window = Window(list_control, wrap_lines=False)
    list_frame = Frame(list_window, title=list_title)

    kb = KeyBindings()

    @kb.add('tab')
    def _tab(e):
        if e.app.layout.has_focus(search_field):
            e.app.layout.focus(list_control)
        else:
            e.app.layout.focus(search_field)

    @kb.add('s-tab')
    def _stab(e):
        if e.app.layout.has_focus(search_field):
            e.app.layout.focus(list_control)
        else:
            e.app.layout.focus(search_field)

    @kb.add('up', filter=has_focus(search_field))
    def _up_search(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] - 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('down', filter=has_focus(search_field))
    def _down_search(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] + 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('up', filter=has_focus(list_control))
    @kb.add('k', filter=has_focus(list_control))
    def _up_list(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] - 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('down', filter=has_focus(list_control))
    @kb.add('j', filter=has_focus(list_control))
    def _down_list(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] + 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('enter')
    def _enter(e):
        if N_filtered[0] > 0:
            act[0] = 'select'
            try:
                e.app.exit()
            except Exception:
                pass

    @kb.add('escape')
    @kb.add('c-c')
    def _quit(e):
        try:
            e.app.exit()
        except Exception:
            pass

    @kb.add('q', filter=has_focus(list_control))
    def _quit_list(e):
        try:
            e.app.exit()
        except Exception:
            pass

    # Bind extra keys — filter to list_control so typing in search box does not trigger shortcuts
    if extra_keys:
        for key_char, action_name in extra_keys.items():
            @kb.add(key_char, filter=has_focus(list_control))
            def _extra(e, act_name=action_name):
                act[0] = act_name
                try:
                    e.app.exit()
                except Exception:
                    pass

            @kb.add(f'c-{key_char}')
            def _extra_ctrl(e, act_name=action_name):
                act[0] = act_name
                try:
                    e.app.exit()
                except Exception:
                    pass

    def get_legend():
        if dialog_app.layout.has_focus(search_field):
            return [
                ('bold white', " MODE: SEARCH  "),
                ('class:dim', "—  Type to filter  |  "),
                ('bold white', "TAB"),
                ('class:dim', " for List Shortcuts  |  "),
                ('bold white', "Ctrl+A/B/D/X"),
                ('class:dim', " Direct Actions  |  "),
                ('bold white', "ESC"),
                ('class:dim', " to quit")
            ]
        else:
            return [
                ('bold white', " MODE: SELECT  "),
                ('class:dim', "—  "),
                ('bold white', "a"),
                ('class:dim', "=Add  "),
                ('bold white', "b"),
                ('class:dim', "=BYOK  "),
                ('bold white', "d"),
                ('class:dim', "=Delete  "),
                ('bold white', "x"),
                ('class:dim', "=Disconnect  |  "),
                ('bold white', "ENTER"),
                ('class:dim', " Select  |  "),
                ('bold white', "TAB"),
                ('class:dim', " Search  |  "),
                ('bold white', "ESC/Q"),
                ('class:dim', " Quit")
            ]

    legend_control = FormattedTextControl(get_legend)
    legend_window = Window(legend_control, height=2)

    layout = Layout(HSplit([
        title_window,
        search_frame,
        list_frame,
        legend_window
    ]))

    dialog_app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({
            'dim': '#888888',
            '': 'bg:#000000 fg:#ffffff',
            'frame.border': '#ffffff',
            'search-field': 'bg:#111111 fg:#ffffff'
        }),
        mouse_support=False,
    )

    update_filtered_rows("", reset_selection=False)
    dialog_app.layout.focus(search_field)
    dialog_app.run()
    _flush_stdin_buffer()

    if act[0] == 'select' and N_filtered[0] > 0:
        orig_idx, selected_row = filtered_rows[sel[0]]
        return 'select', orig_idx
    elif act[0] is not None:
        if N_filtered[0] > 0:
            orig_idx, selected_row = filtered_rows[sel[0]]
            return act[0], orig_idx
        else:
            return act[0], None
    return None, None


def _run_mcp_search_list_dialog(rows, render_row_fn, title="", legend="", search_prompt=" Search Presets: ", search_title="Filter Presets (Search Name, Key, Description, Author, or Package)", list_title="Available MCP Servers", initial_index=0):
    """
    Searchable interactive list dialog specifically for the MCP preset installer.
    Allows real-time search of name/description/pkg, and TAB key toggles focus
    between the search text input and the selection menu.
    """
    if not rows:
        return None, None

    # Flush any lingering key events (e.g. Enter bleed from previous dialog)
    _flush_stdin_buffer()

    sel = [initial_index]
    act = [None]
    viewport_start = [0]
    filtered_rows = []
    N_filtered = [0]

    # Pre-calculate row heights for each of the original rows
    row_heights = []
    for i, row in enumerate(rows):
        try:
            rendered = render_row_fn(i, row, False)
            newlines = sum(text.count('\n') for _, text in rendered)
            row_heights.append(max(1, newlines))
        except Exception:
            row_heights.append(2)

    def update_filtered_rows(query, reset_selection=True):
        nonlocal filtered_rows
        q = query.strip().lower()
        if not q:
            filtered_rows = list(enumerate(rows))
        else:
            filtered_rows = []
            for idx, r in enumerate(rows):
                name = r.get("name", "").lower()
                desc = r.get("desc", "").lower()
                key = r.get("key", "").lower()
                pkg = r.get("pkg", "").lower()
                if q in name or q in desc or q in key or q in pkg:
                    filtered_rows.append((idx, r))
        N_filtered[0] = len(filtered_rows)
        if reset_selection:
            sel[0] = 0
            viewport_start[0] = 0

    def content():
        import shutil
        term_h = shutil.get_terminal_size().lines
        
        # Space layout calculation
        available_height = max(5, term_h - 10)
        
        if N_filtered[0] == 0:
            return [
                ('', '\n'),
                ('bold #f38ba8', '    No matching MCP servers found.\n'),
                ('class:dim', '    Try searching for different keywords (e.g. database, search, maps, slack).\n')
            ]

        matching_heights = [row_heights[orig_idx] for orig_idx, _ in filtered_rows]

        # Slide viewport so that sel[0] is visible
        if sel[0] < viewport_start[0]:
            viewport_start[0] = sel[0]
        else:
            current_height = 0
            for idx in range(viewport_start[0], sel[0] + 1):
                current_height += matching_heights[idx]
            while current_height > available_height and viewport_start[0] < sel[0]:
                current_height -= matching_heights[viewport_start[0]]
                viewport_start[0] += 1

        out = []
        if viewport_start[0] > 0:
            out.append(('class:dim fg:#f9e2af', f'    ▲ ... ({viewport_start[0]} more above) ... ▲\n\n'))
            available_height -= 2

        rendered_height = 0
        end_idx = viewport_start[0]
        while end_idx < N_filtered[0] and rendered_height + matching_heights[end_idx] <= available_height:
            rendered_height += matching_heights[end_idx]
            end_idx += 1

        if end_idx <= sel[0]:
            end_idx = sel[0] + 1

        for i in range(viewport_start[0], end_idx):
            orig_idx, row = filtered_rows[i]
            out.extend(render_row_fn(orig_idx, row, i == sel[0]))

        remaining = N_filtered[0] - end_idx
        if remaining > 0:
            out.append(('class:dim fg:#f9e2af', f'\n    ▼ ... ({remaining} more below) ... ▼\n'))

        return out

    # Title Window
    title_window = Window(FormattedTextControl([('bold #42bcf5', f'\n  {title}\n')]), height=2)

    # Search text area
    search_field = TextArea(
        multiline=False,
        prompt=search_prompt,
        style="class:search-field",
    )
    search_field.buffer.on_text_changed += lambda buf: update_filtered_rows(buf.text)
    search_frame = Frame(search_field, title=search_title)

    # List view
    list_control = FormattedTextControl(content, focusable=True)
    list_window = Window(list_control, wrap_lines=False)
    list_frame = Frame(list_window, title=list_title)

    kb = KeyBindings()

    # Tab navigation to shift focus
    @kb.add('tab')
    def _tab(e):
        if e.app.layout.has_focus(search_field):
            e.app.layout.focus(list_control)
        else:
            e.app.layout.focus(search_field)

    @kb.add('s-tab')
    def _stab(e):
        if e.app.layout.has_focus(search_field):
            e.app.layout.focus(list_control)
        else:
            e.app.layout.focus(search_field)

    # Search mode navigation overrides
    @kb.add('up', filter=has_focus(search_field))
    def _up_search(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] - 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('down', filter=has_focus(search_field))
    def _down_search(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] + 1) % N_filtered[0]
            e.app.invalidate()

    # List mode navigation
    @kb.add('up', filter=has_focus(list_control))
    @kb.add('k', filter=has_focus(list_control))
    def _up_list(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] - 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('down', filter=has_focus(list_control))
    @kb.add('j', filter=has_focus(list_control))
    def _down_list(e):
        if N_filtered[0] > 0:
            sel[0] = (sel[0] + 1) % N_filtered[0]
            e.app.invalidate()

    @kb.add('enter')
    def _enter(e):
        if N_filtered[0] > 0:
            act[0] = 'select'
            try:
                e.app.exit()
            except Exception:
                pass

    @kb.add('escape')
    @kb.add('c-c')
    def _quit(e):
        try:
            e.app.exit()
        except Exception:
            pass

    @kb.add('q', filter=has_focus(list_control))
    def _quit_list(e):
        try:
            e.app.exit()
        except Exception:
            pass

    # Legend text callback based on active focus
    def get_legend():
        if dialog_app.layout.has_focus(search_field):
            return [
                ('bold #a6e3a1', " MODE: SEARCH  "),
                ('class:dim', "—  Type to filter list  |  "),
                ('bold #cba6f7', "TAB"),
                ('class:dim', " to navigate/select  |  "),
                ('bold #f38ba8', "ESC/Q"),
                ('class:dim', " to quit")
            ]
        else:
            return [
                ('bold #f9e2af', " MODE: SELECT  "),
                ('class:dim', "—  Use "),
                ('bold #89b4fa', "UP/DOWN / J/K"),
                ('class:dim', " to navigate  |  "),
                ('bold #a6e3a1', "ENTER"),
                ('class:dim', " to select  |  "),
                ('bold #cba6f7', "TAB"),
                ('class:dim', " to search  |  "),
                ('bold #f38ba8', "ESC/Q"),
                ('class:dim', " to quit")
            ]

    legend_control = FormattedTextControl(get_legend)
    legend_window = Window(legend_control, height=2)

    layout = Layout(HSplit([
        title_window,
        search_frame,
        list_frame,
        legend_window
    ]))

    dialog_app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({
            'dim': '#555577',
            '': 'bg:#0d0d16 fg:#cdd6f4',
            'frame.border': '#89b4fa',
            'search-field': 'bg:#1e1e2e fg:#cdd6f4'
        }),
        mouse_support=False,
    )

    update_filtered_rows("", reset_selection=False)
    dialog_app.layout.focus(search_field)
    dialog_app.run()

    if act[0] == 'select' and N_filtered[0] > 0:
        orig_idx, selected_row = filtered_rows[sel[0]]
        return 'select', orig_idx
    return None, None


# ─── Command dispatch ─────────────────────────────────────────────────────────
def _handle_command(cmd: str, orchestrator: Orchestrator, app_ref) -> None:
    """Handle a slash command. Calls app_ref.exit() on /quit."""
    from utim_cli.config import config
    parts = cmd[1:].split()
    if not parts:
        return
    c = parts[0].lower()

    if c in ("exit", "quit"):
        console.print("\n[bold #42bcf5]Goodbye! See you next time. [/bold #42bcf5]\n")
        app_ref.exit()
        return

    if c == "about":
        from utim_cli import __version__
        def print_about(con):
            con.print()
            con.print(Panel(
                Text.from_markup(
                    f"[bold white]UTIM — Universal Terminal Intelligence Manager[/bold white]\n"
                    f"[dim]Version {__version__}[/dim]\n\n"
                    "The next-generation CLI agent for autonomous software engineering.\n"
                    "Built with [bold #42bcf5]UTIM AI[/bold #42bcf5].\n\n"
                    "[dim]Website:[/dim]  https://utim.dev\n"
                    "[dim]Docs:[/dim]     https://utim.dev/docs"
                ),
                border_style="#42bcf5", padding=(1, 2), expand=False,
            ))
            con.print()
            
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            print_about(console)
        else:
            _run_captured_dialog("UTIM CLI — About", print_about)
        return

    if c == "clear":
        _clear_terminal_screen()
        _print_animated_banner(animated=False)
        # Keep only the system prompt at index 0
        orchestrator.messages = [orchestrator.messages[0]]
        # Also clear turn history since we're clearing conversation
        orchestrator.turn_history = []
        orchestrator._turn_changes = []
        console.print(" [dim]✓ Conversation history and turn history cleared.[/dim]\n")

    elif c == "new":
        _clear_terminal_screen()
        orchestrator.session_id = None
        orchestrator.messages = [orchestrator.messages[0]]
        orchestrator.turn_history = []
        if hasattr(orchestrator, "redo_history"):
            orchestrator.redo_history = []
        orchestrator._turn_changes = []
        STATE.pop("session_id", None)
        STATE.pop("session_topic", None)
        
        # Remove active state file so we don't restore it on next startup
        from utim_cli.config import get_utim_dir as _get_utim_dir
        _ud = _get_utim_dir()
        state_file = _ud / "session_state.json"
        if os.path.exists(state_file):
            try:
                os.remove(state_file)
            except Exception:
                pass
                
        # Remove session usage file as well for a clean new chat
        usage_file = _ud / "session_usage.json"
        if os.path.exists(usage_file):
            try:
                os.remove(usage_file)
            except Exception:
                pass
                
        _print_animated_banner(animated=False)
        console.print(" [bold green]✓ Started a new chat session.[/bold green]\n")

    elif c == "help":
        def print_help(con):
            con.print()
            con.print(Panel(
                Text.from_markup("[bold #42bcf5]UTIM CLI — Slash Commands[/bold #42bcf5]"),
                border_style="#42bcf5", expand=False, padding=(0, 1),
            ))
            user_uid = config.get("firebase_uid") or config.get("uid")
            ALLOWED_FIREBASE_IDS = {"JL763NoYOlRHV5WSkL9ySpz5gkI3", "HADaFqH9p0brRlMAs5mtEbwuBzk1"}

            visible_commands = dict(COMMANDS)
            if user_uid not in ALLOWED_FIREBASE_IDS:
                visible_commands.pop("feedbacks", None)

            for name, desc in visible_commands.items():
                con.print(Text.from_markup(
                    f"  [bold white]/{name.ljust(10)}[/bold white]  [dim]{desc}[/dim]"
                ))
            con.print()
            
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            print_help(console)
        else:
            _run_captured_dialog("UTIM CLI — Help", print_help)

    elif c == "balance":
        from utim_cli.auth import SERVER_URL
        import requests
        api_key = config.get("api_key")
        if not api_key:
            def print_bal(con):
                con.print("\n  [bold red]✗ No UTIM API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
            if type(app_ref).__name__ in ('MagicMock', 'Mock'):
                print_bal(console)
            else:
                _run_captured_dialog("UTIM CLI — Balance", print_bal)
            return

        balance = None
        plan_name = "Free"
        is_subscribed = False
        max_limit = 100.0
        try:
            resp = requests.get(
                f"{SERVER_URL}/api/usage",
                headers={"X-API-Key": api_key},
                timeout=10,
            )
            if resp.ok:
                data = resp.json()
                balance = data.get("balance")
                plan_name = data.get("plan_name", "Free")
                is_subscribed = data.get("is_subscribed", False)
                max_limit = data.get("max_limit", 100.0)
        except Exception:
            pass

        def print_bal(con):
            con.print()
            if balance is not None:
                if is_subscribed:
                    con.print(f"  Active Plan: [bold cyan]{plan_name}[/bold cyan]")
                    con.print(f"  Five Hour Quota: [bold green]{data.get('five_hour_quota_percent', 0.0):.2f}%[/bold green]")
                    con.print(f"  Quota Bank: [bold green]{data.get('quota_bank_percent', 0.0):.2f}%[/bold green]")
                    con.print(f"  Bonus Quota: [bold green]{data.get('bonus_quota_percent', 0.0):.2f}%[/bold green] (Credits available: [bold green]{data.get('bonus_balance', 0.0):.1f}[/bold green] / Max allowed: [bold white]{data.get('bonus_limit', 0.0):.0f}[/bold white])")
                else:
                    con.print(f"  Active Plan: [bold cyan]Free Tier[/bold cyan]")
                    con.print(f"  Compute Balance: [bold green]{balance:.2f} / {max_limit:.2f} credits[/bold green]")
            else:
                con.print("  [bold red]✗ Failed to check balance from server.[/bold red]")
                con.print("  Please make sure you have a valid connection to the Railway backend.")
            con.print()

        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            print_bal(console)
        else:
            _run_captured_dialog("UTIM CLI — Balance", print_bal)

    elif is_wheel_command(c):
        def _render_wheel_flow(con):
            from utim_cli.tui.rewards_tui import run_rewards_cli_flow
            run_rewards_cli_flow(con)

        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            execute_wheel_cli_flow()
        else:
            _run_captured_dialog("UTIM Rewards Wheel", _render_wheel_flow)
        return

    elif c == "status":
        def print_status(con):
            msg_count = len(orchestrator.messages)
            con.print()
            con.print(Panel(
                Text.from_markup(f"[bold white]Session Stats[/bold white]\n\n  [dim]Messages:[/dim]  {msg_count}"),
                border_style="dim", padding=(0, 2), expand=False,
            ))
            con.print()
            
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            print_status(console)
        else:
            _run_captured_dialog("UTIM CLI — Status", print_status)

    elif c == "usage":
        from utim_cli.auth import SERVER_URL
        import requests
        api_key = config.get("api_key")
        if not api_key:
            console.print("  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
            return

        try:
            resp = requests.get(
                f"{SERVER_URL}/api/usage",
                headers={"X-API-Key": api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            console.print(f"  [bold red]✗ Failed to fetch usage from server: {exc}[/bold red]\n")
            return

        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            render_usage_menu(data)
        else:
            _run_usage_dialog(data)

    elif c == "hint":
        hint_text = " ".join(parts[1:])
        if not hint_text:
            console.print("\n  [bold red]✗ Please provide a hint message.[/bold red]")
            console.print("  Usage: [bold]/hint <your directive or cheat text>[/bold]\n")
            return

        if STATE.get("busy"):
            # Agent is mid-turn: inject into STATE so the next system prompt
            # build (which happens on every LLM API call iteration) picks it up.
            STATE["hint"] = hint_text
            if "hint_messages" not in STATE or not isinstance(STATE["hint_messages"], list):
                STATE["hint_messages"] = []
            STATE["hint_messages"].append(hint_text)
            console.print(f"\n  [bold #e5ff00][+] LIVE HINT SENT:[/bold #e5ff00] \"{hint_text}\"")
            console.print("  [dim]Injected into the active model call — agent will follow it on its next reasoning step.[/dim]\n")
        else:
            # Agent is idle: fire the hint immediately as a real task so the
            # user doesn't have to send another message to trigger it.
            directive = f"[HINT DIRECTIVE — follow this instruction immediately]: {hint_text}"
            console.print(f"\n  [bold #e5ff00][+] HINT FIRED IMMEDIATELY:[/bold #e5ff00] \"{hint_text}\"")
            console.print("  [dim]Running now — no need to send another message.[/dim]\n")

            STATE["busy"] = True
            STATE["busy_start"] = __import__("time").time()
            STATE["_task_gen"] = STATE.get("_task_gen", 0) + 1
            my_gen = STATE["_task_gen"]

            def _run_hint_task():
                try:
                    orchestrator.run_task(directive)
                except Exception:
                    pass
                if STATE.get("_task_gen", my_gen) == my_gen:
                    STATE["busy"] = False
                    try:
                        app_ref.invalidate()
                    except Exception:
                        pass

            import threading as _threading
            _threading.Thread(target=_run_hint_task, daemon=True, name="utim-hint-task").start()
            try:
                app_ref.invalidate()
            except Exception:
                pass

    elif c == "rewind":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='rewind')
        else:
            _dialog_rewind(orchestrator)

    elif c == "undo":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            STATE["command_args"] = parts[1:]
            app_ref.exit(result='undo')
        else:
            _action_undo(orchestrator, parts[1:])

    elif c == "redo":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            STATE["command_args"] = parts[1:]
            app_ref.exit(result='redo')
        else:
            _action_redo(orchestrator, parts[1:])

    elif c == "resume":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='resume')
        else:
            loaded = _dialog_resume(orchestrator)
            if loaded:
                _clear_terminal_screen()
                _print_animated_banner(animated=False)
                _print_session_history(orchestrator, loaded, STATE.get('session_topic', ''))
                orchestrator._persist_messages()

    elif c == "model":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='model')
        else:
            _dialog_model(orchestrator)

    elif c == "modelsettings":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='modelsettings')
        else:
            _dialog_modelsettings(orchestrator)

    elif c == "mcp":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='mcp')
        else:
            _dialog_mcp(orchestrator)

    elif c == "doctor":
        def print_doc(con):
            from utim_cli.doctor import run_diagnostics
            run_diagnostics(con)
            
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            print_doc(console)
        else:
            _run_captured_dialog("UTIM CLI — Doctor Diagnostics", print_doc)

    elif c == "report":
        def print_rep(con):
            from utim_cli.report import create_report_bundle
            con.print("\n  [bold yellow]Generating redacted diagnostic support bundle...[/bold yellow]")
            try:
                bundle_path = create_report_bundle()
                con.print(f"  [bold green]✓ Support report bundle created successfully![/bold green]")
                con.print(f"  Saved to: [bold white]{bundle_path}[/bold white]\n")
            except Exception as e:
                con.print(f"  [bold red]✗ Failed to create support bundle: {e}[/bold red]\n")
                
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            print_rep(console)
        else:
            _run_captured_dialog("UTIM CLI — Support Report", print_rep)

    elif c == "tools":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='tools')
        else:
            _dialog_tools(orchestrator)

    elif c == "skills":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='skills')
        else:
            tag = _dialog_skills(orchestrator)
            if tag:
                STATE["pending_input_prefix"] = tag

    elif c == "subagents":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='subagents')
        else:
            from utim_cli.tui.subagents_dialog import _dialog_subagents
            tag = _dialog_subagents(orchestrator)
            if tag:
                STATE["pending_input_prefix"] = tag

    elif c == "miniagents":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='miniagents')
        else:
            from utim_cli.tui.miniagents_dialog import _dialog_miniagents
            tag = _dialog_miniagents(orchestrator)
            if tag:
                STATE["pending_input_prefix"] = tag

    elif c == "marketplace":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='marketplace')
        else:
            from utim_cli.tui.marketplace_dialog import _dialog_marketplace
            _dialog_marketplace(orchestrator)

    elif c == "autoupdate":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='autoupdate')
        else:
            _dialog_auto_update()

    elif c == "share":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='share')
        else:
            from utim_cli.share_tui import run_share_flow
            run_share_flow(orchestrator)

    elif c == "quota":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='quota')
        else:
            from utim_cli.tui.quota_dialog import _dialog_quota
            _dialog_quota(orchestrator)

    elif c == "quotashare":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='quotashare')
        else:
            from utim_cli.tui.quota_share_dialog import run_quota_share_flow
            _run_full_screen_flow(run_quota_share_flow, orchestrator)

    elif c == "redeem":
        if type(app_ref).__name__ in ('MagicMock', 'Mock'):
            app_ref.exit(result='redeem')
        else:
            from utim_cli.tui.quota_redeem_dialog import run_quota_redeem_flow
            _run_full_screen_flow(run_quota_redeem_flow, orchestrator)

    elif c == "chatrestore":
        current = config.get("restore_session_state", True)
        new_val = not current
        config.set("restore_session_state", new_val)
        console.print(f"\n[bold green]✓ Session state auto-restoration on startup has been {'enabled' if new_val else 'disabled'}.[/bold green]\n")
        if not new_val:
            console.print("[dim]Next time you boot UTIM, it will start with a fresh new chat session.[/dim]\n")

    elif c == "sslverify":
        current = config.get("verify_ssl", True)
        new_val = not current
        config.set("verify_ssl", new_val)
        # Apply the patch live — no restart needed.
        from utim_cli.config import _apply_ssl_session_patch
        _apply_ssl_session_patch(disable=not new_val)
        console.print(f"\n[bold green]✓ SSL certificate verification has been {'enabled' if new_val else 'disabled'}.[/bold green]")
        console.print("[dim]Change is effective immediately — no restart needed.[/dim]\n")

    elif c == "rate":
        from utim_cli.tui.feedback_dialog import _dialog_submit_feedback
        _dialog_submit_feedback(orchestrator)

    elif c in ("feedbacks", "feedback"):
        user_uid = config.get("firebase_uid") or config.get("uid")
        ALLOWED_FIREBASE_IDS = {"JL763NoYOlRHV5WSkL9ySpz5gkI3", "HADaFqH9p0brRlMAs5mtEbwuBzk1"}
        if user_uid not in ALLOWED_FIREBASE_IDS:
            console.print("\n[bold red]✗ Command not found.[/bold red]\n")
        else:
            from utim_cli.tui.feedback_dialog import _dialog_feedbacks
            _dialog_feedbacks(orchestrator)

    elif c == "login":
        if config.token and config.email and config.email.upper() != "GUEST":
            console.print(f"\n[yellow]You are already logged in as [bold]{config.email}[/bold].[/yellow]")
            console.print("[dim]Run [white]/logout[/white] first if you want to switch accounts.[/dim]\n")
        else:
            def _do_login():
                try:
                    auth.login(restart=True)
                except Exception as exc:
                    console.print(f"\n  [bold red]✗ Login failed: {exc}[/bold red]\n")
            _run_in_terminal_safe(_do_login)
            orchestrator.email = config.email
            orchestrator.token = config.token

            # Fetch user plan immediately after login
            api_key = config.get("api_key")
            user_type = "UTIM Community"
            if api_key:
                try:
                    from utim_cli.auth import SERVER_URL
                    import requests
                    resp = requests.get(
                        f"{SERVER_URL}/api/user-plan",
                        headers={"X-API-Key": api_key},
                        timeout=5.0,
                    )
                    if resp.ok:
                        plan_name = resp.json().get("plan", "free")
                        config.set("user_plan", plan_name)
                        PLAN_NAME_MAP = {
                            "free": "Free",
                            "hobby": "Hobbyist Node",
                            "pro": "Starter Node",
                            "max": "Professional Core",
                            "ultimate": "MAX Node"
                        }
                        user_type = f"UTIM {PLAN_NAME_MAP.get(plan_name.lower().strip(), plan_name.title())}"
                except Exception:
                    pass

            console.print(f"\n  [bold green]✓ Successfully logged in as:[/bold green] [bold white]{config.email}[/bold white]")
            console.print(f"  [dim]{config.email}  •  {user_type}[/dim]\n")

    elif c == "logout":
        if not config.token:
            console.print("\n[dim]You are already logged out.[/dim]\n")
        else:
            config.clear()
            console.print("\n[bold #f9e2af]✓ Successfully logged out.[/bold #f9e2af]\n")
            orchestrator.email = config.email
            orchestrator.token = config.token

    elif c == "auth":
        import getpass, pathlib, os as _os
        from utim_cli.config import get_utim_dir
        global_dir = get_utim_dir()
        global_env = global_dir / ".env"

        # Show current status
        current_key = _os.getenv("OPENROUTER_API_KEY", "")
        if current_key:
            masked = current_key[:8] + "•" * max(0, len(current_key) - 12) + current_key[-4:]
            console.print(f"\n  [dim]Current key:[/dim] [bold #42bcf5]{masked}[/bold #42bcf5]")
        else:
            console.print("\n  [dim yellow]No API key configured.[/dim yellow]")

        console.print(
            f"\n  [dim]Keys are saved to global env:[/dim] [dim #42bcf5]{global_env}[/dim #42bcf5]\n"
            "  [dim]Get a free key at [/dim][bold #42bcf5]https://openrouter.ai[/bold #42bcf5]\n"
        )

        try:
            new_key = getpass.getpass("  Enter new OpenRouter API key (Enter to cancel): ").strip()
        except (EOFError, KeyboardInterrupt):
            new_key = ""

        if not new_key:
            console.print("\n[dim]Cancelled.[/dim]\n")
        else:
            # Save to global
            global_dir.mkdir(parents=True, exist_ok=True)
            try:
                existing = global_env.read_text(encoding="utf-8").splitlines() if global_env.exists() else []
                lines = [l for l in existing if not l.startswith("OPENROUTER_API_KEY=")]
                lines.append(f"OPENROUTER_API_KEY={new_key}")
                global_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
            except Exception as e:
                console.print(f"[dim yellow]Could not write to global env: {e}[/dim yellow]")

            # Activate immediately in this session
            import os as _os2
            _os2.environ["OPENROUTER_API_KEY"] = new_key
            orchestrator._local_client = True
            console.print("\n[bold #f9e2af]✓ API key saved and active.[/bold #f9e2af]\n")

    else:
        console.print(f"\n[bold red]Unknown command:[/bold red] {cmd}")
        console.print("[dim]Type /help for a list of available commands.[/dim]\n")


# ─── Dialog runners (called from start_chat restart loop) ──────────────────────────────

def _prompt_input(prompt_text: str, secure: bool = False) -> str:
    from prompt_toolkit import prompt
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        return prompt(prompt_text, is_password=secure)
    except (KeyboardInterrupt, EOFError):
        return ""

from utim_cli.tui.model_dialog import (
    _dialog_model, 
    _dialog_subagents_menu, 
    _dialog_model_main, 
    _dialog_byok_import, 
    _dialog_add_custom_model, 
    _dialog_delete_custom_model, 
    _dialog_disconnect_provider,
    _dialog_modelsettings
)

from utim_cli.tui.mcp_dialog import _dialog_mcp, _dialog_mcp_manage, _dialog_mcp_install
from utim_cli.tui.tools_dialog import _dialog_tools
from utim_cli.tui.skills_dialog import _dialog_skills



def _transient_status(lines: list, hold: float = 1.5):
    """
    Print *lines* (list of Rich-markup strings) to stdout, wait `hold` seconds,
    then erase every printed line so nothing stays in the chat buffer.
    """
    import sys, time as _time
    rendered_lines = []
    for ln in lines:
        console.print(ln, no_wrap=True, crop=True)
        # With no_wrap=True, each print occupies exactly 1 terminal line
        rendered_lines.append(1)
    _time.sleep(hold)
    # Erase upward: for each rendered line move cursor up and clear the line
    total = len(rendered_lines)
    for _ in range(total):
        sys.stdout.write("\x1b[1A\x1b[2K")
    sys.stdout.flush()










from utim_cli.tui.resume_dialog import _dialog_resume


def _is_system_note(content) -> bool:
    if not content:
        return False
    if isinstance(content, list):
        text = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    else:
        text = str(content)
    text = text.strip()
    return (
        "### SYSTEM NOTE:" in text
        or "[System Note:" in text
        or "Context Stabilization Summary" in text
        or "TASK STATE ANCHOR" in text
        or "INTERMEDIATE STEPS COMPRESSED" in text
        or "[SYSTEM DIRECTIVE]" in text
    )

def _print_session_history(orchestrator, messages, topic):
    """Print the last few turns of a resumed session so the user has immediate context."""
    from rich.rule import Rule
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text
    from rich.markup import escape
    
    def _extract_text(content) -> str:
        if isinstance(content, list):
            return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        return str(content or "")

    # We want to reprint the last 4 turns for a good balance of context without flooding
    history = orchestrator.turn_history
    recent_turns = list(history[-8:]) if history else []

    # If there are leftover messages (in-progress turn), append them as a mock turn
    last_end = history[-1].get("msg_end", 0) if history else 0
    if len(messages) > last_end:
        leftover_slice = messages[last_end:]
        has_content = any(m.get("role") in ("user", "assistant", "tool") for m in leftover_slice if not _is_system_note(m.get("content")))
        if has_content:
            user_msg = next((m.get("content", "") for m in leftover_slice if m.get("role") == "user" and not _is_system_note(m.get("content"))), "")
            if isinstance(user_msg, list):
                user_msg = " ".join(p.get("text", "") for p in user_msg if isinstance(p, dict))
            recent_turns.append({
                "user_msg": user_msg,
                "msg_start": last_end,
                "msg_end": len(messages),
                "messages": leftover_slice
            })
            recent_turns = recent_turns[-8:]
    
    if not recent_turns:
        # Fallback if no turn_history (e.g. legacy resumes or blank states)
        turns = [
            (m['role'], _extract_text(m.get('content')))
            for m in messages
            if m.get('role') in ('user', 'assistant') and m.get('content') and not _is_system_note(m.get('content'))
        ]
        recent = turns[-10:]
        if not recent:
            return
            
        w = min(console.size.width - 4, 100)
        console.print()
        console.print(Rule(f'[dim #42bcf5] ↺  {escape(topic[:65])} [/dim #42bcf5]', style='dim #42bcf5'))
        console.print()
        for role, content in recent:
            if role == 'user':
                preview = content.strip()[:220] + ('\u2026' if len(content.strip()) > 220 else '')
                console.print(f'[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] {escape(preview)}')
            else:
                preview = content.strip()[:500] + ('\u2026' if len(content.strip()) > 500 else '')
                console.print(Markdown(preview), width=w)
            console.print()
        console.print(Rule('[dim]Continue below[/dim]', style='dim'))
        console.print()
        return

    w = min(console.size.width - 4, 100)
    console.print()
    console.print(Rule(
        f'[dim #42bcf5] ↺  {escape(topic[:65])} [/dim #42bcf5]',
        style='dim #42bcf5',
    ))
    console.print()

    # Iterate over recent turns to render chronologically with tool calls
    for turn in recent_turns:
        t_start = turn.get("msg_start", 0)
        t_end = turn.get("msg_end", 0)
        turn_msgs = turn.get("messages") or messages[t_start:t_end]
        
        # Map tool call results by ID and by function name as fallback
        tool_results_map = {}
        tool_results_by_name = {}
        for m in turn_msgs:
            if m.get("role") == "tool":
                tc_id = m.get("tool_call_id")
                if tc_id:
                    tool_results_map[tc_id] = m
                fname = m.get("name")
                if fname:
                    tool_results_by_name.setdefault(fname, []).append(m)
                
        for m in turn_msgs:
            role = m.get("role")
            content = m.get("content") or ""
            
            if role == "user":
                if _is_system_note(content):
                    continue
                preview = _extract_text(content).strip()
                if not preview:
                    continue
                console.print(f'[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] {escape(preview)}')
                console.print()
                
            elif role == "assistant":
                if content.strip():
                    console.print(Markdown(content.strip()), width=w)
                    console.print()
                    
                tool_calls = m.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        tc_id = tc.get("id") or str(tc.get("index", "0"))
                        func_name = tc.get("function", {}).get("name") or tc.get("name", "")
                        if not func_name:
                            continue
                        
                        tool_msg = tool_results_map.get(tc_id)
                        if not tool_msg and func_name in tool_results_by_name and tool_results_by_name[func_name]:
                            tool_msg = tool_results_by_name[func_name].pop(0)

                        import json
                        try:
                            args_raw = tc.get("function", {}).get("arguments") if "function" in tc else tc.get("arguments", "{}")
                            args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                        except Exception:
                            args = {}

                        res_str = tool_msg.get("content", "") if tool_msg else ""
                        
                        color = orchestrator.TOOL_COLOR.get(func_name, "white") if hasattr(orchestrator, "TOOL_COLOR") else "white"
                        if color == "white":
                            from utim_cli.orchestrator import TOOL_COLOR as _tc_map
                            color = _tc_map.get(func_name, "cyan")
                            
                        orchestrator._render_result(func_name, args, res_str, color, expand=STATE.get("tools_expanded", False))
                        console.print()

    try:
        from utim_cli.tui.thinking_display import global_thinking_manager
        thinking_block = global_thinking_manager.render(console)
        if thinking_block:
            console.print(thinking_block)
    except Exception:
        pass
                            
    console.print(Rule('[dim]Continue below[/dim]', style='dim'))
    console.print()



from utim_cli.tui.history_dialog import (
    _dialog_rewind,
    _dialog_undo,
    _dialog_redo
)

def _action_undo(orchestrator, args=None):
    if not args:
        _dialog_undo(orchestrator)
        return

    try:
        n = int(args[0])
    except ValueError:
        console.print(f"\n[bold red]✗ Invalid argument:[/bold red] '{args[0]}' is not a valid number of turns.")
        return

    if n <= 0:
        console.print("\n[bold red]✗ Invalid argument:[/bold red] Please specify a positive number of turns to undo.")
        return

    history = orchestrator.turn_history
    if not history:
        console.print("\n[dim yellow]No active turns to undo.[/dim yellow]\n")
        return

    n = min(n, len(history))
    idx = len(history) - n

    console.print(f"\n[dim]⌛ Undoing last {n} turn(s)...[/dim]")
    res = orchestrator.rewind_to_turn(idx, revert_code=True, revert_msgs=True)
    orchestrator._persist_messages()
    
    _clear_terminal_screen()
    parts = [f'[bold #a6e3a1]\u2713 Undo complete ({n} turn(s) reverted).[/bold #a6e3a1]']
    if res.get('reverted'):
        parts.append(f"  [dim]Reverted: {', '.join(res['reverted'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))
    
    # Reprint whatever conversation remains after the undo
    remaining = orchestrator.messages
    if remaining:
        turns = [
            (m['role'], m.get('content') or '')
            for m in remaining
            if m.get('role') in ('user', 'assistant') and m.get('content')
        ]
        if turns:
            from rich.rule import Rule
            from rich.markdown import Markdown
            w = min(console.size.width - 4, 100)
            console.print()
            console.print(Rule('[dim #42bcf5] ↶  Conversation after undo [/dim #42bcf5]', style='dim #42bcf5'))
            console.print()
            for role, content in turns:
                if role == 'user':
                    preview = content.strip()[:220] + ('\u2026' if len(content.strip()) > 220 else '')
                    console.print(f'[bold #42bcf5]❯[/bold #42bcf5] {preview}')
                else:
                    preview = content.strip()[:500] + ('\u2026' if len(content.strip()) > 500 else '')
                    console.print(Markdown(preview), width=w)
                console.print()
            console.print(Rule('[dim]Continue below[/dim]', style='dim'))
    console.print()


def _action_redo(orchestrator, args=None):
    if not args:
        _dialog_redo(orchestrator)
        return

    try:
        n = int(args[0])
    except ValueError:
        console.print(f"\n[bold red]✗ Invalid argument:[/bold red] '{args[0]}' is not a valid number of turns.")
        return

    if n <= 0:
        console.print("\n[bold red]✗ Invalid argument:[/bold red] Please specify a positive number of turns to redo.")
        return

    redo_hist = getattr(orchestrator, "redo_history", [])
    if not redo_hist:
        console.print("\n[dim yellow]No undone turns to redo.[/dim yellow]\n")
        return

    n = min(n, len(redo_hist))
    redo_idx = n - 1

    console.print(f"\n[dim]⌛ Redoing next {n} turn(s)...[/dim]")
    res = orchestrator.redo_up_to_turn(redo_idx)
    
    _clear_terminal_screen()
    parts = [f'[bold #a6e3a1]\u2713 Redo complete ({n} turn(s) redone).[/bold #a6e3a1]']
    if res.get('redone_code'):
        parts.append(f"  [dim]Redone: {', '.join(res['redone_code'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))
    
    # Reprint whatever conversation remains after the redo
    remaining = orchestrator.messages
    if remaining:
        turns = [
            (m['role'], m.get('content') or '')
            for m in remaining
            if m.get('role') in ('user', 'assistant') and m.get('content')
        ]
        if turns:
            from rich.rule import Rule
            from rich.markdown import Markdown
            w = min(console.size.width - 4, 100)
            console.print()
            console.print(Rule('[dim #42bcf5] ↷  Conversation after redo [/dim #42bcf5]', style='dim #42bcf5'))
            console.print()
            for role, content in turns:
                if role == 'user':
                    preview = content.strip()[:220] + ('\u2026' if len(content.strip()) > 220 else '')
                    console.print(f'[bold #42bcf5]❯[/bold #42bcf5] {preview}')
                else:
                    preview = content.strip()[:500] + ('\u2026' if len(content.strip()) > 500 else '')
                    console.print(Markdown(preview), width=w)
                console.print()
            console.print(Rule('[dim]Continue below[/dim]', style='dim'))
    console.print()


# ─── Main Chat (sticky input via prompt_toolkit Application) ───────────────────────────

# Prompt history — persists across dialog restarts (lives at module level)
_prompt_history: list = []   # list of submitted prompt strings (oldest first)

# Reference to the current running pt_app (set inside _build_pt_app, cleared on exit)
_pt_app_ref = [None]

# Set to True while a _manual_confirm dialog is being shown.
# The spinner loop reads this to pause invalidation and avoid overwriting the dialog.
_confirm_active = [False]
_confirm_state = {
    "options": [],
    "selected": 0,
    "event": threading.Event(),
    "choice": None,
    "rendered": False
}

def _render_confirm_menu_lines():
    import sys
    options = _confirm_state.get("options", [])
    selected = _confirm_state.get("selected", 0)
    for i, opt in enumerate(options):
        if i == selected:
            sys.stdout.write(f"  \x1b[1;32m▶  {opt}\x1b[0m\n")
        else:
            sys.stdout.write(f"     \x1b[2m{opt}\x1b[0m\n")
    sys.stdout.flush()
    _confirm_state["rendered"] = True

def _erase_confirm_menu_lines():
    import sys
    if not _confirm_state.get("rendered"):
        return
    n = len(_confirm_state.get("options", []))
    for _ in range(n):
        sys.stdout.write("\x1b[1A\x1b[2K")
    sys.stdout.flush()
    _confirm_state["rendered"] = False

_run_queue_lock = threading.Lock()

# ─── Live shell panel content ─────────────────────────────────────────────────
from .tools import _SHELL_STATE as _SHELL

def _register_app_with_shell(app):
    """Tell the tools module which app to invalidate when shell output arrives."""
    _SHELL["_app_ref"][0] = app

def _get_shell_panel_content():
    """Returns FormattedText for the live shell panel."""
    cmd_short = _SHELL["cmd"]
    if len(cmd_short) > 55:
        cmd_short = cmd_short[:52] + "..."
    cwd_short = _SHELL["cwd"]
    home = os.path.expanduser("~")
    if cwd_short.startswith(home):
        cwd_short = "~" + cwd_short[len(home):]
    if len(cwd_short) > 30:
        cwd_short = "..." + cwd_short[-27:]

    focused = _SHELL["focused"]
    hint = "  (Shift+Tab to unfocus)" if focused else "  (Tab to focus)"
    hint_style = "class:shell-focused-hint" if focused else "class:shell-header-dim"
    border_style = "#a6e3a1" if focused else "#313244"

    out = []
    # Header line
    arrow = "←" if focused else "←"
    out.append(("class:shell-header", f" {arrow} Shell "))
    out.append(("class:shell-header-dim", f"{cmd_short}"))
    out.append(("class:shell-header-dim", f"  [in {cwd_short}]"))
    out.append((hint_style, hint + "\n"))

    # Output lines (last 12)
    term_w = shutil.get_terminal_size().columns - 2
    for raw_line in _SHELL["output_lines"][-12:]:
        line = raw_line.rstrip()
        if len(line) > term_w:
            line = line[:term_w - 1] + "…"
        out.append(("", f" {line}\n"))

    return out


def _read_arrow_choice(options: list, timeout_seconds: float = 60.0) -> int:
    """
    Cross-platform interactive arrow-key menu.
    Renders `options` with a ▶ cursor, moves on Up/Down, confirms on Enter.
    Auto-declines (returns index of last option: reject/cancel) if no input is received within timeout_seconds (default 60s).
    Clears the rendered lines before returning so the dialog vanishes.
    Returns the 0-based index of the selected option.
    """
    import sys, os, time

    selected = 0
    n = len(options)
    start_time = time.time()

    # Write directly to the real stdout bypassing _StdoutProxy / patch_stdout buffering.
    # On Windows, sys.__stdout__ may be CP1252 so we write UTF-8 bytes to .buffer when available.
    _raw = getattr(sys.__stdout__, "buffer", None) if sys.__stdout__ else None

    def _out_write(s: str):
        if _raw is not None:
            _raw.write(s.encode("utf-8", errors="replace"))
            _raw.flush()
        else:
            target = sys.__stdout__ or sys.stdout
            try:
                target.write(s)
                target.flush()
            except UnicodeEncodeError:
                target.write(s.encode("ascii", errors="replace").decode("ascii"))
                target.flush()

    def _render():
        for i, opt in enumerate(options):
            if i == selected:
                _out_write(f"  \x1b[1;32m>  {opt}\x1b[0m\n")
            else:
                _out_write(f"     \x1b[2m{opt}\x1b[0m\n")

    def _clear(lines):
        """Erase `lines` lines upward."""
        for _ in range(lines):
            _out_write("\x1b[1A\x1b[2K")  # cursor up + erase line

    try:
        import msvcrt  # Windows
        _render()
        while True:
            if timeout_seconds and (time.time() - start_time >= timeout_seconds):
                _clear(n)
                _out_write("  ⏱ Command auto-declined (60s timeout — no user response)\n")
                return n - 1  # auto-decline / reject

            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ('\r', '\n'):             # Enter
                    _clear(n)
                    return selected
                elif ch in ('y', 'Y'):             # Accept hotkey
                    _clear(n)
                    return 0
                elif ch in ('n', 'N', 'q', 'Q'):   # Reject hotkey
                    _clear(n)
                    return n - 1
                elif ch in ('k', 'w', 'K', 'W'):   # Up
                    _clear(n)
                    selected = (selected - 1) % n
                    _render()
                elif ch in ('j', 's', 'J', 'S'):   # Down
                    _clear(n)
                    selected = (selected + 1) % n
                    _render()
                elif ch == '\x1b':                 # Escape or ANSI sequence
                    time.sleep(0.01)
                    if msvcrt.kbhit():
                        ch2 = msvcrt.getwch()
                        if ch2 in ('[', 'O'):
                            if msvcrt.kbhit():
                                ch3 = msvcrt.getwch()
                                if ch3 == 'A':     # Up arrow (ANSI)
                                    _clear(n)
                                    selected = (selected - 1) % n
                                    _render()
                                    continue
                                elif ch3 == 'B':   # Down arrow (ANSI)
                                    _clear(n)
                                    selected = (selected + 1) % n
                                    _render()
                                    continue
                    # Bare Esc key
                    _clear(n)
                    return n - 1
                elif ch in ('\xe0', '\x00'):       # special Win32 key prefix
                    ch2 = msvcrt.getwch()
                    if ch2 in ('H', '7'):          # Up arrow / Home
                        _clear(n)
                        selected = (selected - 1) % n
                        _render()
                    elif ch2 in ('P', '8'):        # Down arrow / End
                        _clear(n)
                        selected = (selected + 1) % n
                        _render()
            else:
                time.sleep(0.02)
    except ImportError:
        # Unix / macOS fallback
        import tty, termios, select
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            _render()
            while True:
                if timeout_seconds and (time.time() - start_time >= timeout_seconds):
                    _clear(n)
                    _out_write("  ⏱ Command auto-declined (60s timeout — no user response)\n")
                    return n - 1

                rlist, _, _ = select.select([sys.stdin], [], [], 0.02)
                if rlist:
                    ch = sys.stdin.read(1)
                    if ch in ('\r', '\n'):         # Enter
                        _clear(n)
                        return selected
                    elif ch in ('y', 'Y'):         # Accept
                        _clear(n)
                        return 0
                    elif ch in ('n', 'N', 'q', 'Q'): # Reject
                        _clear(n)
                        return n - 1
                    elif ch in ('k', 'w', 'K', 'W'): # Up
                        _clear(n)
                        selected = (selected - 1) % n
                        _render()
                    elif ch in ('j', 's', 'J', 'S'): # Down
                        _clear(n)
                        selected = (selected + 1) % n
                        _render()
                    elif ch == '\x1b':             # Escape or arrow prefix
                        rlist_seq, _, _ = select.select([sys.stdin], [], [], 0.01)
                        if rlist_seq:
                            seq = sys.stdin.read(2)
                            if seq in ('[A', 'OA'):        # Up
                                _clear(n)
                                selected = (selected - 1) % n
                                _render()
                            elif seq in ('[B', 'OB'):      # Down
                                _clear(n)
                                selected = (selected + 1) % n
                                _render()
                            else:                  # bare Escape
                                _clear(n)
                                return n - 1
                        else:                      # bare Escape
                            _clear(n)
                            return n - 1
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _manual_confirm(tool_name: str, arguments: dict, diff_lines: list = None) -> str:
    """Show a styled confirmation panel with arrow-key navigation and wait for Accept/Reject.

    Returns one of:
        'allow'          — allow this single action
        'allow_session'  — allow all remaining actions this session (disable manual)
        'reject'         — skip this tool call; tell the model it was rejected
    Called from the orchestrator's background worker thread.
    """
    _confirm_active[0] = True
    res = ["reject"]

    def _do_confirm():
        res[0] = _manual_confirm_internal(tool_name, arguments, diff_lines)

    try:
        # Run inside _run_in_terminal_safe so prompt_toolkit suspends its UI renderer thread
        # and leaves sys.stdin and sys.stdout completely clear for the interactive dialog.
        _run_in_terminal_safe(_do_confirm)
        return res[0]
    finally:
        _confirm_active[0] = False
        app = _pt_app_ref[0]
        if app is not None:
            try:
                app.invalidate()
            except Exception:
                pass


def _manual_confirm_internal(tool_name: str, arguments: dict, diff_lines: list = None) -> str:
    from rich.text import Text as _Text
    from rich.panel import Panel as _Panel
    import sys

    # Flush lingering keypresses
    _flush_stdin_buffer()

    # ── Build a path/summary line ─────────────────────────────────────────
    path = (
        arguments.get("filepath")
        or arguments.get("path")
        or arguments.get("file")
        or arguments.get("TargetFile")
        or arguments.get("destination")
        or arguments.get("dst")
        or ""
    )
    src  = arguments.get("source") or arguments.get("src", "")

    label_map = {
        "write_file":  "Write",
        "edit_file":   "Edit",
        "delete_file": "Delete",
        "move_file":   "Move",
        "run_command": "Run",
    }
    label = label_map.get(tool_name, f"●  {tool_name}")

    if tool_name == "move_file" and src and path:
        target_str = f"{src}  →  {path}"
    elif tool_name == "run_command":
        target_str = (
            arguments.get("command")
            or arguments.get("cmd")
            or arguments.get("CommandLine")
            or arguments.get("shell")
            or arguments.get("script")
            or (", ".join(arguments.get("commands")) if isinstance(arguments.get("commands"), list) else None)
            or (str(arguments) if arguments else "(no command specified)")
        )
    else:
        target_str = path or "(unknown path)"

    # ── Diff preview ──────────────────────────────────────────────────────
    body = _Text()

    if tool_name == "run_command":
        import utim_cli.tools as _t
        is_safe, reason = _t.analyze_command_safety(target_str)
        # ── Session-level safe-command bypass ─────────────────────────────
        if is_safe and STATE.get("session_allow_safe_cmds"):
            _t.approve_command(target_str)
            return "allow"
        if is_safe:
            body.append(f"? {label} (Safe):  ", style="bold green")
            body.append(target_str, style="bold white")
            border_style = "green"
            title_text = "[bold green]Action Required — Safe Command[/bold green]"
        else:
            body.append(f"? {label} (Risky):  ", style="bold red")
            body.append(target_str, style="bold white")
            body.append(f"\n  Classification Reason: {reason}", style="bold red")
            border_style = "red"
            title_text = "[bold red]Action Required — Risky Command[/bold red]"
        body.append("\nExecute this terminal command?", style="bold white")
        menu_options = [
            "Accept (run command)",
            "Accept + auto-allow safe commands this session",
            "Reject (cancel)",
        ]
    else:
        body.append(f"? {label}:  ", style="bold yellow")
        body.append(target_str, style="bold white")
        if diff_lines:
            body.append("\n")
            for dl in diff_lines[:10]:   # up to 10 context lines
                if dl.startswith("+"):
                    body.append(f"  {dl}\n", style="bold green")
                elif dl.startswith("-"):
                    body.append(f"  {dl}\n", style="bold red")
                else:
                    body.append(f"  {dl}\n", style="dim white")
            if len(diff_lines) > 10:
                body.append(f"  … ({len(diff_lines)-10} more lines)\n", style="dim")
        body.append("\nApply this change?", style="bold white")
        border_style = "yellow"
        title_text = "[bold yellow]Action Required[/bold yellow]"
        menu_options = [
            "Allow once",
            "Allow for this session",
            "No, reject",
        ]

    # ── Print panel (cleared after selection) ─────────────────────────────
    # Use a fresh Console bound to sys.__stdout__ (the real fd-1) so the panel
    # is rendered immediately, bypassing _StdoutProxy / patch_stdout buffering.
    import sys as _sys
    from rich.console import Console as _Console
    _direct_console = _Console(
        force_terminal=True,
        highlight=False,
        file=_sys.__stdout__,
        width=get_console_width(),
    )
    _direct_console.print()
    _direct_console.print(_Panel(
        body,
        title=title_text,
        border_style=border_style,
        padding=(0, 2),
    ))
    # Write hint line directly to the real stdout buffer (UTF-8 safe on Windows)
    _direct_raw = getattr(_sys.__stdout__, "buffer", None) if _sys.__stdout__ else None
    def _confirm_write(s: str):
        if _direct_raw is not None:
            _direct_raw.write(s.encode("utf-8", errors="replace"))
            _direct_raw.flush()
        else:
            try:
                _sys.__stdout__.write(s)
                _sys.__stdout__.flush()
            except (UnicodeEncodeError, AttributeError):
                pass

    _confirm_write("  Use ^ v / J K to navigate, Enter to confirm, Esc / Q / N to reject  (60s timeout)\n")

    # ── Arrow-key menu ──────────────────────────────────────────────────
    choice = _read_arrow_choice(menu_options, timeout_seconds=60.0)   # 0, 1, or 2

    # Erase the hint line printed above
    _confirm_write("\x1b[1A\x1b[2K")

    if choice == 0:    # Allow once
        if tool_name == "run_command":
            import utim_cli.tools as _t
            _t.approve_command(target_str)
        _direct_console.print("[dim]  ✓ Allowed[/dim]\n")
        return "allow"
    elif choice == 1:  # Allow session / auto-allow safe
        if tool_name == "run_command":
            import utim_cli.tools as _t
            _t.approve_command(target_str)
            # Mark that safe commands should be auto-allowed for the rest of the session
            STATE["session_allow_safe_cmds"] = True
            _direct_console.print("[dim green]  ✓ Allowed for session — safe commands will auto-run[/dim green]\n")
        else:
            _direct_console.print("[dim green]  ✓ Allowed for session — auto-accepting remaining changes[/dim green]\n")
            STATE["mode"] = "auto-accept edits"
        return "allow_session"
    else:              # Reject / Escape
        if tool_name == "run_command":
            _direct_console.print("[dim red]  ✗ Command rejected[/dim red]\n")
        else:
            _direct_console.print("[dim red]  ✗ Change rejected[/dim red]\n")
        return "reject"

def _find_image_paths(line):
    import os, re
    results = []
    
    # 1. Find quoted paths
    quoted_pattern = r'("[^"]+"|\'[^\']+\')'
    for m in re.finditer(quoted_pattern, line):
        path = m.group(1)[1:-1]
        if path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
            if os.path.isfile(path):
                results.append((m.start(), m.end(), path, True))
                
    # 2. Find unquoted paths by looking backwards from extensions
    ext_pattern = r'(?i)(\.(?:png|jpg|jpeg|gif|webp|bmp))(?!\w)'
    for m in re.finditer(ext_pattern, line):
        end_idx = m.end()
        if any(start <= end_idx <= end for start, end, _, _ in results):
            continue
            
        prefix_text = line[:end_idx]
        parts = prefix_text.split(' ')
        
        valid_path = None
        valid_start = -1
        current_path_parts = []
        
        for i in range(len(parts)-1, -1, -1):
            current_path_parts.insert(0, parts[i])
            test_path = ' '.join(current_path_parts)
            if os.path.isfile(test_path):
                valid_path = test_path
                valid_start = end_idx - len(test_path)
                break
            if test_path.startswith('@') and os.path.isfile(test_path[1:]):
                valid_path = test_path[1:]
                valid_start = end_idx - len(test_path) + 1
                break
                
        if valid_path:
            results.append((valid_start, end_idx, valid_path, False))
            
    results.sort(key=lambda x: x[0])
    return results

import re as _re
_AT_TAG_PATTERN = _re.compile(r'(?:^|(?<=\s))(@[\w-]+)')

_AT_VALID_IDS_CACHE = {'ids': set(), 'ts': 0.0}

def _get_valid_at_ids():
    """Return set of valid @-tag IDs for blue syntax highlighting."""
    import time as _time_mod
    now = _time_mod.monotonic()
    if now - _AT_VALID_IDS_CACHE['ts'] > 1.0:
        # Only exact options in the dropdown turn blue!
        base_ids = {"miniagents", "skills"}
        try:
            from utim_cli.tui.miniagents_dialog import _load_miniagents
            for a in _load_miniagents():
                base_ids.add(a["id"].lower())
        except Exception:
            pass
        try:
            from utim_cli.tui.miniagents_dialog import _load_miniagents
            for a in _load_miniagents():
                base_ids.add(a["id"].lower())
        except Exception:
            pass
        try:
            from utim_cli.tui.skills_dialog import _load_skills
            skills, _ = _load_skills()
            for s in skills:
                base_ids.add(s["name"].lower())
        except Exception:
            pass
        _AT_VALID_IDS_CACHE['ids'] = base_ids
        _AT_VALID_IDS_CACHE['ts'] = now
    return _AT_VALID_IDS_CACHE['ids']


class ImagePathLexer(Lexer):
    """Lexer that colors image paths green and valid @<id> tags blue.
    A @tag is only colored blue when its id exactly matches a known
    subagent, miniagent, or skill — checked via the cached valid-id set.
    """
    def lex_document(self, document):
        def get_line(lineno):
            line = document.lines[lineno]
            # 1) Collect image path regions
            img_results = _find_image_paths(line)
            # 2) Collect @tag regions — only when id is a known entity
            valid_ids = _get_valid_at_ids()
            at_results = []
            for m in _AT_TAG_PATTERN.finditer(line):
                g = m.group(1)       # e.g. '@refactor-bot'
                agent_id = g[1:]     # strip '@'
                if agent_id in valid_ids:
                    start = m.start(1)
                    at_results.append((start, start + len(g)))

            # 3) Collect workspace file/folder path regions
            ws_results = []
            import os as _os
            for m in _re.finditer(r'("[^"]+"|\'[^\']+\')', line):
                p = m.group(1)[1:-1]
                if _os.path.exists(p) and not p.startswith(('@', '/')):
                    ws_results.append((m.start(), m.end(), 'class:hash-file'))

            for m in _re.finditer(r'(?:^|(?<=\s))([^\s@\/#][^\s]*\/[^\s]*|[^\s@\/#][^\s]*\.[a-zA-Z0-9]+)', line):
                p = m.group(1)
                if _os.path.exists(p):
                    start = m.start(1)
                    ws_results.append((start, start + len(p), 'class:hash-file'))

            # Build sorted (start, end, style) list
            regions = []
            for start, end, path, is_quoted in img_results:
                regions.append((start, end, 'class:image-path'))
            for start, end in at_results:
                regions.append((start, end, 'class:at-tag'))
            for start, end, style in ws_results:
                regions.append((start, end, style))
            regions.sort(key=lambda r: r[0])

            tokens = []
            last_end = 0
            for start, end, style in regions:
                if start < last_end:
                    continue
                if start > last_end:
                    tokens.append(('', line[last_end:start]))
                tokens.append((style, line[start:end]))
                last_end = end
            if last_end < len(line):
                tokens.append(('', line[last_end:]))
            return tokens
        return get_line

def confirm_y_n(prompt_text: str) -> bool:
    from prompt_toolkit import prompt
    try:
        user_input = prompt(prompt_text)
        return user_input.strip().lower() in ('y', 'yes', '')
    except (KeyboardInterrupt, EOFError):
        return False

def _is_standalone_share_input(text: str) -> bool:
    """Return True only when the input is a bare UTIM share link/ID.

    A share link by itself (optionally wrapped in quotes, brackets, or with
    surrounding whitespace) is treated as a download command. If the link is
    embedded within other prose (e.g. "check this link <share link>"), it is
    treated as a normal prompt instead.
    """
    stripped = text.strip()
    if not stripped:
        return False
    # Remove a single layer of common wrapping (quotes, angle/paren/square brackets)
    if len(stripped) >= 2 and stripped[0] in "\"'([<" and stripped[-1] in "\"')]>":
        inner = stripped[1:-1].strip()
        # Only unwrap if the closing char matches the opening char
        pairs = {'"': '"', "'": "'", '(': ')', '[': ']', '<': '>'}
        if pairs.get(stripped[0]) == stripped[-1]:
            stripped = inner
    # After unwrapping, the entire input must be exactly one share token,
    # or a full share download URL containing nothing but that token.
    if re.fullmatch(r"share_[a-f0-9]{12}", stripped):
        return True
    # Full URL form: <scheme>://<host>/shares/download/share_xxxx
    _m = re.search(r"share_[a-f0-9]{12}", stripped)
    if not _m:
        return False
    # Only accept if the token is the last path segment of a /shares/download/ URL
    return bool(re.fullmatch(r"https?://[^\s/]+/shares/download/share_[a-f0-9]{12}", stripped))


def handle_download_share(url_or_id: str, dest_dir: str = "."):
    import re
    import requests
    import zipfile
    import io
    import os

    share_id_match = re.search(r"share_[a-f0-9]{12}", url_or_id)
    if not share_id_match:
        return

    share_id = share_id_match.group(0)
    server_url = os.getenv("UTIM_SERVER_URL", "https://api.utim.dev").rstrip("/")
    download_url = f"{server_url}/shares/download/{share_id}"

    # Clear screen first so download flow starts cleanly at the top of the terminal
    _clear_terminal_screen()

    target_abs = os.path.abspath(dest_dir)
    console.print(f"\n  [bold cyan]Detected UTIM share link/ID: {share_id}[/bold cyan]")
    console.print(f"  Do you want to download and extract this shared project into [bold white]{target_abs}[/bold white]?\n")
    if not confirm_y_n("  Confirm download and extraction? (Y/n): "):
        console.print("\n  [yellow]Download cancelled.[/yellow]\n")
        return

    from utim_cli.share import print_progress_bar
    import sys

    # 1. Stream download and show progress bar
    try:
        resp = requests.get(download_url, stream=True, timeout=30)
        if resp.status_code == 404:
            console.print("  [bold red]✗ Error: Shared package does not exist or has expired.[/bold red]\n")
            return
        elif resp.status_code == 410:
            console.print("  [bold red]✗ Error: This shared package has expired.[/bold red]\n")
            return
        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0))
        zip_data = io.BytesIO()
        downloaded = 0

        # Stream download chunks
        for chunk in resp.iter_content(chunk_size=4096):
            if chunk:
                zip_data.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    print_progress_bar(100.0 * downloaded / total_size, "Downloading:")
                else:
                    sys.__stdout__.write(f"\r  Downloading: {downloaded / 1024:.1f} KB")
                    sys.__stdout__.flush()
        sys.__stdout__.write("\n")
        sys.__stdout__.flush()
    except Exception as exc:
        console.print(f"  [bold red]✗ Failed to download shared package: {exc}[/bold red]\n")
        return

    # 2. Extract files individually and show progress bar
    try:
        zip_data.seek(0)
        # Pre-check: verify the downloaded bytes are actually a ZIP archive
        # (guards against error HTML pages or network-truncated responses)
        magic = zip_data.read(4)
        zip_data.seek(0)
        # ZIP magic bytes: PK\x03\x04 (local file header) or PK\x05\x06 (empty) or PK\x07\x08
        if not magic.startswith(b'PK'):
            console.print(
                "  [bold red]✗ The downloaded file is not a valid ZIP archive.[/bold red]\n"
                "  [dim]This usually means the share link has expired, the package was corrupted during upload,\n"
                "  or the server returned an error page. Ask the sender to re-share.[/dim]\n"
            )
            return

        with zipfile.ZipFile(zip_data) as zip_ref:
            infolist = zip_ref.infolist()
            total_items = len(infolist)
            extracted = 0

            for item in infolist:
                zip_ref.extract(item, dest_dir)
                extracted += 1
                if total_items > 0:
                    print_progress_bar(100.0 * extracted / total_items, "Extracting:")
            
            sys.__stdout__.write("\n")
            sys.__stdout__.flush()

        console.print("\n  [bold green]✓ Successfully downloaded and extracted shared project files![/bold green]")
        if os.path.exists("chat_history.md"):
            console.print("  [dim]Check [white]chat_history.md[/white] to view the shared conversation.[/dim]")
        console.print()
    except zipfile.BadZipFile:
        console.print(
            "  [bold red]✗ Failed to extract package: The downloaded file is corrupt or not a ZIP.[/bold red]\n"
            "  [dim]The share may have expired, or the file was damaged during transfer.\n"
            "  Ask the sender to create a new share link.[/dim]\n"
        )
    except Exception as exc:
        console.print(f"  [bold red]✗ Failed to extract package: {exc}[/bold red]\n")

    confirm_y_n("  Press Enter to return...")



def _handle_input_text_changed(buffer):
    from prompt_toolkit.document import Document
    text = buffer.text
    
    results = _find_image_paths(text)
    if not results:
        return
        
    cursor = buffer.cursor_position
    new_text = text
    shift = 0
    changed = False
    
    for start, end, path, is_quoted in reversed(results):
        if not is_quoted:
            new_text = new_text[:start] + '"' + new_text[start:end] + '"' + new_text[end:]
            changed = True
            if cursor >= end:
                shift += 2
            elif cursor > start:
                shift += 1
                
    if changed:
        buffer.document = Document(new_text, cursor + shift)

def _build_pt_app(orchestrator, last_sigint, initial_prompt=None):
    """Build and return a fresh prompt_toolkit Application.
    Called each time we restart after a dialog closes.
    """
    _pt_app_ref[0] = None   # cleared until we have the app object


    _combined_completer = CombinedCompleter()
    from prompt_toolkit.layout.dimension import Dimension as D
    input_field = TextArea(
        prompt=[('class:input-prompt', f' {PROMPT_SYMBOL}  ')],
        style='class:input-field',
        multiline=True,
        wrap_lines=True,
        completer=_combined_completer,
        complete_while_typing=Condition(
            lambda: (
                input_field.text.lstrip().startswith('/') or
                input_field.text.lstrip().startswith('@') or
                '#' in input_field.text
            )
        ),
        dont_extend_height=True,
        height=D(min=1, max=12),
        scrollbar=False,

        lexer=ImagePathLexer(),
        input_processors=[PlaceholderProcessor('Type "/" for menu  •  @tag for agent  •  #file for files')],
        read_only=Condition(lambda: _confirm_active[0]),
    )
    
    def _handle_text_changed_with_preprompt(buffer):
        try:
            orchestrator.pre_prompt_text = buffer.text
        except Exception:
            pass
        _handle_input_text_changed(buffer)

    # Auto-quote valid image paths
    input_field.buffer.on_text_changed += _handle_text_changed_with_preprompt

    # History navigation state (per app instance)
    # cursor: index into _prompt_history (-1 = at live draft)
    # draft: text saved before the user first pressed Up
    _hist_state = {"cursor": -1, "draft": ""}
    
    tool_view_area = TextArea(read_only=True, scrollbar=True)

    kb = KeyBindings()

    @kb.add('up', filter=Condition(lambda: _confirm_active[0]))
    @kb.add('k', filter=Condition(lambda: _confirm_active[0]))
    def _confirm_up(event):
        _erase_confirm_menu_lines()
        _confirm_state["selected"] = (_confirm_state["selected"] - 1) % max(1, len(_confirm_state["options"]))
        _render_confirm_menu_lines()

    @kb.add('down', filter=Condition(lambda: _confirm_active[0]))
    @kb.add('j', filter=Condition(lambda: _confirm_active[0]))
    def _confirm_down(event):
        _erase_confirm_menu_lines()
        _confirm_state["selected"] = (_confirm_state["selected"] + 1) % max(1, len(_confirm_state["options"]))
        _render_confirm_menu_lines()

    @kb.add('enter', filter=Condition(lambda: _confirm_active[0]))
    def _confirm_enter(event):
        _erase_confirm_menu_lines()
        _confirm_state["choice"] = _confirm_state["selected"]
        _confirm_state["event"].set()

    @kb.add('y', filter=Condition(lambda: _confirm_active[0]))
    @kb.add('Y', filter=Condition(lambda: _confirm_active[0]))
    def _confirm_accept(event):
        _erase_confirm_menu_lines()
        _confirm_state["choice"] = 0
        _confirm_state["event"].set()

    @kb.add('n', filter=Condition(lambda: _confirm_active[0]))
    @kb.add('N', filter=Condition(lambda: _confirm_active[0]))
    @kb.add('escape', filter=Condition(lambda: _confirm_active[0]))
    @kb.add('q', filter=Condition(lambda: _confirm_active[0]))
    def _confirm_reject(event):
        _erase_confirm_menu_lines()
        _confirm_state["choice"] = max(0, len(_confirm_state["options"]) - 1)
        _confirm_state["event"].set()

    @kb.add('c-o')
    def _on_ctrl_o(event):
        if _confirm_active[0]:
            return
        from utim_cli.state import STATE
        STATE["tools_expanded"] = not STATE.get("tools_expanded", False)
        try:
            from utim_cli.tui.thinking_display import global_thinking_manager
            global_thinking_manager.toggle_expand()
        except Exception:
            pass

        def toggle_inline():
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))

        _run_in_terminal_safe(toggle_inline)
        event.app.invalidate()

    @kb.add('tab')
    def _on_tab(event):
        if _SHELL["active"] and not _SHELL["focused"]:
            _SHELL["focused"] = True
            event.app.invalidate()

    @kb.add('s-tab')
    def _toggle_mode(event):
        if _SHELL["focused"]:
            _SHELL["focused"] = False
        else:
            STATE["mode"] = "manual" if STATE["mode"] == "auto-accept edits" else "auto-accept edits"
        event.app.invalidate()

    @kb.add('up')
    def _on_up(event):
        if _confirm_active[0]:
            return
        buf = input_field.buffer
        if buf.complete_state:
            buf.complete_previous()
            return

        cur_row = buf.document.cursor_position_row
        
        # If we have multiple lines, move cursor up
        if cur_row > 0:
            buf.cursor_up()
            return
            
        # We are on the first logical line (row 0).
        # We only load history if:
        # 1. The input field is empty, OR
        # 2. The cursor is at the very beginning of the buffer (index 0).
        if buf.cursor_position == 0 or not buf.text:
            if STATE.get("busy") and STATE.get("queue"):
                item = STATE["queue"].pop()
                if _prompt_history and _prompt_history[-1] == item:
                    _prompt_history.pop()
                input_field.text = item
                input_field.buffer.cursor_position = len(item)
                event.app.invalidate()
                return

            if not _prompt_history:
                return

            if _hist_state["cursor"] == -1:
                _hist_state["draft"] = input_field.text
            new_cursor = _hist_state["cursor"] + 1
            max_idx = len(_prompt_history) - 1
            if new_cursor > max_idx:
                new_cursor = max_idx
            _hist_state["cursor"] = new_cursor
            entry = _prompt_history[-(new_cursor + 1)]
            input_field.text = entry
            buf.cursor_position = len(entry)
            event.app.invalidate()
        else:
            # Cursor is in the middle of the first line: just move to start of line
            buf.cursor_position = 0
            event.app.invalidate()

    @kb.add('down')
    def _on_down(event):
        if _confirm_active[0]:
            return
        buf = input_field.buffer
        if buf.complete_state:
            buf.complete_next()
            return

        cur_row = buf.document.cursor_position_row
        total_rows = buf.document.line_count
        
        # If we have multiple lines and are not on the last line, move cursor down
        if cur_row < total_rows - 1:
            buf.cursor_down()
            return

        # We are on the last line.
        # We only load next history/draft if:
        # 1. The input field is empty, OR
        # 2. The cursor is at the very end of the buffer.
        if buf.cursor_position == len(buf.text) or not buf.text:
            if _hist_state["cursor"] == -1:
                return
            new_cursor = _hist_state["cursor"] - 1
            if new_cursor < 0:
                _hist_state["cursor"] = -1
                draft = _hist_state["draft"]
                input_field.text = draft
                input_field.buffer.cursor_position = len(draft)
            else:
                _hist_state["cursor"] = new_cursor
                entry = _prompt_history[-(new_cursor + 1)]
                input_field.text = entry
                input_field.buffer.cursor_position = len(entry)
            event.app.invalidate()
        else:
            # Cursor is in the middle of the last line: just move to end of line
            buf.cursor_position = len(buf.text)
            event.app.invalidate()

    @kb.add('c-a')
    def _select_all(event):
        buf = event.current_buffer
        buf.cursor_position = 0
        buf.start_selection()
        buf.cursor_position = len(buf.text)
        event.app.invalidate()

    # ── Shift + Arrow Selection Keybindings ──

    @kb.add('s-left')
    def _select_left(event):
        buf = event.current_buffer
        if not buf.selection_state:
            buf.start_selection()
        buf.cursor_left()

    @kb.add('s-right')
    def _select_right(event):
        buf = event.current_buffer
        if not buf.selection_state:
            buf.start_selection()
        buf.cursor_right()

    @kb.add('s-up')
    def _select_up(event):
        buf = event.current_buffer
        if not buf.selection_state:
            buf.start_selection()
        buf.cursor_up()

    @kb.add('s-down')
    def _select_down(event):
        buf = event.current_buffer
        if not buf.selection_state:
            buf.start_selection()
        buf.cursor_down()

    @kb.add('s-home')
    def _select_home(event):
        buf = event.current_buffer
        if not buf.selection_state:
            buf.start_selection()
        buf.cursor_position = buf.document.get_start_of_line_position()

    @kb.add('s-end')
    def _select_end(event):
        buf = event.current_buffer
        if not buf.selection_state:
            buf.start_selection()
        buf.cursor_position = len(buf.text)

    @kb.add('backspace')
    @kb.add('c-h')
    def _backspace(event):
        from prompt_toolkit.document import Document
        buf = event.current_buffer
        if buf.selection_state:
            from_pos, to_pos = buf.document.selection_range()
            new_text = buf.text[:from_pos] + buf.text[to_pos:]
            buf.document = Document(new_text, from_pos)
        else:
            if buf.cursor_position > 0:
                cp = buf.cursor_position
                new_text = buf.text[:cp - 1] + buf.text[cp:]
                buf.document = Document(new_text, cp - 1)

    @kb.add('delete')
    def _delete(event):
        from prompt_toolkit.document import Document
        buf = event.current_buffer
        if buf.selection_state:
            from_pos, to_pos = buf.document.selection_range()
            new_text = buf.text[:from_pos] + buf.text[to_pos:]
            buf.document = Document(new_text, from_pos)
        else:
            if buf.cursor_position < len(buf.text):
                cp = buf.cursor_position
                new_text = buf.text[:cp] + buf.text[cp + 1:]
                buf.document = Document(new_text, cp)

    @kb.add('escape')
    def _on_escape(event):
        if _confirm_active[0]:
            return
        if STATE.get("tool_view", {}).get("active"):
            STATE["tool_view"]["active"] = False
            event.app.layout.focus(input_field)
            print('\033[2J\033[H', end='')
            event.app.invalidate()
            return
            
        if STATE["busy"]:
            STATE["queue"] = []
            STATE["busy"] = False
            STATE["thinking_topic"] = ""
            STATE["busy_start"] = None
            STATE["_task_gen"] = STATE.get("_task_gen", 0) + 1
            orchestrator.abort()

            import threading
            def send_cancel_to_server():
                try:
                    import requests
                    from utim_cli.auth import SERVER_URL
                    from utim_cli.config import config
                    session_id = getattr(orchestrator, "session_id", None)
                    api_key = config.get("api_key")
                    if api_key:
                        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
                        requests.post(f"{SERVER_URL}/completions/cancel", json={"session_id": session_id}, headers=headers, timeout=1.0)
                except Exception:
                    pass
            threading.Thread(target=send_cancel_to_server, daemon=True).start()
            console.print("\n[dim yellow]⊘  Aborted.[/dim yellow]")
        else:
            input_field.text = ""
            _hist_state["cursor"] = -1
            _hist_state["draft"] = ""
        event.app.invalidate()

    @kb.add('c-b')
    def _on_ctrl_b(event):
        if _SHELL["active"]:
            from .tools import shell_send_to_background
            shell_send_to_background()
            return

    @kb.add('c-c')
    def _on_ctrl_c(event):
        if _confirm_active[0]:
            return
        if _SHELL["active"] and _SHELL["focused"]:
            from .tools import shell_send_ctrl_c
            shell_send_ctrl_c()
            return

        now = time.time()
        # use the module-level last_sigint list
        double_press = (now - last_sigint[0]) < 1.0
        last_sigint[0] = now
        STATE["last_ctrl_c"] = now

        if double_press:
            sys.stdout.write("\n\033[1;34mGoodbye! See you next time.\033[0m\n\n")
            sys.stdout.flush()
            import os
            os._exit(0)

        if STATE["busy"]:
            STATE["queue"] = []
            STATE["busy"] = False
            STATE["thinking_topic"] = ""
            STATE["busy_start"] = None
            STATE["_task_gen"] = STATE.get("_task_gen", 0) + 1
            orchestrator.abort()
            
            import threading
            def send_cancel_to_server():
                try:
                    import requests
                    from utim_cli.auth import SERVER_URL
                    from utim_cli.config import config
                    session_id = getattr(orchestrator, "session_id", None)
                    api_key = config.get("api_key")
                    if api_key:
                        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
                        requests.post(f"{SERVER_URL}/completions/cancel", json={"session_id": session_id}, headers=headers, timeout=1.0)
                except Exception:
                    pass
            threading.Thread(target=send_cancel_to_server, daemon=True).start()

            sys.stdout.write("\n\033[33m⊘  Aborted.\033[0m\n")
            sys.stdout.flush()
        else:
            input_field.text = ""
            sys.stdout.write("\n\033[2m(Press Ctrl+C again to exit)\033[0m\n")
            sys.stdout.flush()
        event.app.invalidate()

    @kb.add('<any>', eager=False, filter=Condition(lambda: _SHELL["focused"]))
    def _shell_passthrough(event):
        from .tools import shell_send_input
        key_seq = event.key_sequence
        for kp in key_seq:
            k = kp.key
            if hasattr(k, 'value'):
                k = k.value
            if k == 'enter':            shell_send_input("\n")
            elif k == 'c-c':            pass
            elif k == 'c-d':            shell_send_input("\x04")
            elif k == 'backspace':      shell_send_input("\x7f")
            elif k == 's-tab':          pass
            elif k == 'tab':            shell_send_input("\t")
            elif k == 'up':             shell_send_input("\x1b[A")
            elif k == 'down':           shell_send_input("\x1b[B")
            elif k == 'left':           shell_send_input("\x1b[D")
            elif k == 'right':          shell_send_input("\x1b[C")
            elif len(k) == 1:           shell_send_input(k)
        event.app.invalidate()

    def _submit_current_text(event):
        text = input_field.text.strip()
        input_field.text = ''
        _hist_state["cursor"] = -1
        _hist_state["draft"] = ""

        if not text:
            return

        if text.startswith('/'):
            # Strip to just the command word (e.g. "/res" → "/resume" after completion)
            cmd_word = text.split()[0].lower()
            # If incomplete slash command with no match, try to find best prefix match
            bare = cmd_word.lstrip('/')
            if bare and bare not in COMMANDS:
                match = next((c for c in COMMANDS if c.startswith(bare)), None)
                if match:
                    cmd_word = '/' + match
                    # Replace the first word of text with the matched command word
                    words = text.split()
                    words[0] = cmd_word
                    text = " ".join(words)
            cmd_name = cmd_word.lstrip('/')
            CONCURRENT_COMMANDS = {"rewards", "usage", "hint", "tools", "skills", "subagents", "miniagents", "marketplace", "help", "about", "doctor", "report", "chatrestore", "sslverify", "rate", "feedback", "feedbacks", "quota", "quotashare", "redeem"}
            if STATE["busy"] and cmd_name not in CONCURRENT_COMMANDS:
                console.print(f"\n[dim yellow]Cannot execute command {text} while agent is busy.[/dim yellow]")
                return
            def _exec_cmd():
                _handle_command(text, orchestrator, event.app)

            _run_in_terminal_safe(_exec_cmd)
            pending_prefix = STATE.pop("pending_input_prefix", None)
            if pending_prefix:
                input_field.text = pending_prefix
            return

        # ── @tag handling: set active system prompt override without stripping tag from chat display ──
        import re
        _at_token_match = re.match(r'^(@[\w-]+)\s*(.*)', text, re.DOTALL)
        if _at_token_match:
            _at_tag = _at_token_match.group(1).lower()   # e.g. '@miniagents'
            _at_rest = _at_token_match.group(2).strip()
            _tag_id = _at_tag[1:]  # strip '@'

            _MINIAGENTS_ENHANCED_PROMPT = """You are the UTIM Miniagent Tool Architect & Senior Developer.
Miniagents are custom executable tools stored in `.utim/miniagents/<id>/` that the LLM (main UTIM model) can call during chat — just like built-in tools (`analyze_image`, `run_command`, etc.) but created on demand.

## File layout
.utim/miniagents/<id>/
├── agent.json   ← tool schema (id, name, description, lang, main, parameters)
├── agent.py     ← main executable (or index.js for Node)
└── helpers.py   ← (optional) shared utilities

## agent.json — must be valid JSON, NO comments
{"id":"<id>","name":"miniagent_<id>","description":"<precise description of what this does and when the LLM should call it>","lang":"python","main":"agent.py","parameters":{"type":"object","properties":{"arg":{"type":"string","description":"..."}},"required":["arg"]}}

## agent.py — execution contract
UTIM runs: python agent.py '<json-args-string>'
The script MUST: parse sys.argv[1] as JSON → do real work → print result to stdout → exit 0.

Always use this boilerplate:
```python
import sys, json, os

def main():
    args = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    # implement the real logic here (HTTP, file I/O, subprocess, LLM, etc.)
    print(result)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
```

## Workflow
1. If the request is vague or requires an API/key you don't know → ASK the user before writing code.
2. Pick an id, define parameter schema, choose implementation (HTTP / subprocess / file I/O / LLM via OpenRouter).
3. Create dir, write agent.json, write agent.py, write README.md (documentation for marketplace publication).
4. Confirm: tool name, parameters, any pip packages the user needs to install.

## Rules (non-negotiable)
- ALWAYS create a comprehensive `README.md` alongside `agent.py` describing the mini-agent's features, usage, and commands.
- NEVER create agent.json without agent.py — the script IS the tool.
- NEVER leave placeholders (`pass`, `# TODO`). Write real, working code.
- NEVER assume env vars exist — use os.getenv() and print a clear error if missing.
- ALWAYS print to stdout — that's what the LLM sees as the tool result."""

            _SKILLS_ENHANCED_PROMPT = """You are the UTIM Skill Guidelines Architect & Prompt Engineer.
Your primary role is to author modular, high-impact skill guideline packs for UTIM CLI.

## Skill Architecture & File Structure
name: <skill-name>             # Kebab-case identifier (e.g. "react-patterns", "async-python")
description: <string>          # Clear trigger criteria explaining EXACTLY when UTIM should activate this skill
---

# <Skill Title>

## Overview
<High-level summary of domain, technology stack, and objectives>

## Core Guidelines & Principles
- **Rule 1**: <Imperative, concrete rule with clear rationale>
- **Rule 2**: <Imperative, concrete rule with clear rationale>
- **Rule 3**: <Imperative, concrete rule with clear rationale>

## Recommended Patterns & Code Examples
```<language>
<Production-ready, battle-tested code implementation>
```

## Anti-Patterns & Pitfalls to Avoid
- **Avoid**: <Common mistake>
- **Correction**: <Proper alternative>

## Operational Checklist
- [ ] Verification step 1
- [ ] Verification step 2

## Your Workflow
1. **Identify Domain & Trigger Criteria**: Define the skill scope, name, and exact prompt triggers.
2. **Create Storage Folder**: Ensure directory `.utim/skills/<skill-name>/` exists.
3. **Write Guideline Files**:
- Write `.utim/skills/<skill-name>/SKILL.md` with YAML frontmatter and comprehensive guidelines.
- Write `.utim/skills/<skill-name>/README.md` containing full documentation, trigger criteria, and usage examples for marketplace listing.
4. **Confirm to User**: Display a summary of the skill name, trigger criteria, and file paths."""

            _CREATION_PROMPTS = {
                "miniagents": _MINIAGENTS_ENHANCED_PROMPT,
                "miniagent": _MINIAGENTS_ENHANCED_PROMPT,
                "skills": _SKILLS_ENHANCED_PROMPT,
                "skill": _SKILLS_ENHANCED_PROMPT,
            }


            if _tag_id in _CREATION_PROMPTS:
                orchestrator.active_tag = _at_tag
                orchestrator.active_tag_system_prompt = _CREATION_PROMPTS[_tag_id]
            else:
                # Check created miniagents, skills
                _found_sp = None
                _found_model = None
                try:
                    from utim_cli.tui.miniagents_dialog import _load_miniagents, get_miniagent_model_by_size
                    for a in _load_miniagents():
                        if a["id"].lower() == _tag_id:
                            _found_sp = a["system_prompt"]
                            _found_model = a.get("primary_model") or get_miniagent_model_by_size(a.get("path"))
                            break
                except Exception:
                    pass

                if not _found_sp:
                    try:
                        from utim_cli.tui.skills_dialog import _load_skills
                        skills, _ = _load_skills()
                        for s in skills:
                            if s["name"].lower() == _tag_id:
                                _found_sp = s["content"]
                                break
                    except Exception:
                        pass

                if _found_sp:
                    orchestrator.active_tag = _at_tag
                    orchestrator.active_tag_system_prompt = _found_sp
                    if _found_model:
                        orchestrator.set_model(_found_model)
                else:
                    orchestrator.active_tag = None
                    orchestrator.active_tag_system_prompt = None
        else:
            orchestrator.active_tag = None
            orchestrator.active_tag_system_prompt = None

        # Check if the user pasted ONLY a UTIM share URL/ID (no other text).
        # If the share link is embedded within a larger prompt (e.g. "check this
        # link <share link>"), treat it as a normal prompt instead of a download.
        _share_match = re.search(r"share_[a-f0-9]{12}", text)
        if _share_match and _is_standalone_share_input(text):
            _run_in_terminal_safe(lambda: handle_download_share(text, dest_dir=os.getcwd()))
            return

        is_logged_in = bool(config.token and config.email and config.email.upper() != "GUEST")
        if not is_logged_in:
            console.print("\n  [bold red]✗ Authentication Required.[/bold red] You must log in before sending a prompt.")
            def run_auth_login():
                try:
                    auth.login(restart=True)
                except Exception as exc:
                    console.print(f"\n  [bold red]✗ Login failed: {exc}[/bold red]\n")
            _run_in_terminal_safe(run_auth_login)
            # Restore their prompt text so they don't have to retype it
            input_field.text = text
            return

        if not _prompt_history or _prompt_history[-1] != text:
            _prompt_history.append(text)

        if STATE["busy"]:
            STATE.setdefault("queue", []).append(text)
            event.app.invalidate()
            return

        # Pasted text threshold: show preview instead of full text if too long
        lines = text.splitlines()
        if len(lines) > 15 or len(text) > 1000:
            line_count = len(lines)
            char_count = len(text)
            _echo_line = f"[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] [Pasted Text: {line_count} lines, {char_count} chars]\n{escape(text[:200])}{'...' if len(text) > 200 else ''}"
        else:
            _echo_line = f"[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] {escape(text)}"

        def _start_task():
            console.print(_echo_line)
            console.print()

        _run_in_terminal_safe(_start_task)

        STATE["busy"] = True
        STATE["busy_start"] = time.time()
        _next_tip()
        event.app.invalidate()

        # Generation counter: each new task spawn increments this so the old
        # aborting thread self-exits immediately without holding any lock.
        STATE["_task_gen"] = STATE.get("_task_gen", 0) + 1
        my_gen = STATE["_task_gen"]

        def _run_queue():
            current_text = text
            start_time = time.time()
            while current_text:
                # Bail out if a newer task generation has taken over
                if STATE.get("_task_gen", my_gen) != my_gen:
                    return
                try:
                    orchestrator.run_task(current_text)
                except Exception as e:
                    import traceback
                    console.print(f"\n[bold red]Task Execution Error: {e}[/bold red]")
                    console.print(traceback.format_exc())

                # Stop processing queue if we were superseded
                if STATE.get("_task_gen", my_gen) != my_gen:
                    return

                queue = STATE.get("queue", [])
                if queue:
                    current_text = queue.pop(0)
                    console.print(f"\n[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] {escape(current_text)}")
                    console.print()
                    STATE["busy_start"] = time.time()
                else:
                    current_text = None

            # Only update busy=False if we are still the active generation
            if STATE.get("_task_gen", my_gen) == my_gen:
                STATE["busy"] = False
                try:
                    event.app.invalidate()
                except Exception:
                    pass

            elapsed = time.time() - start_time
            if elapsed > 240:
                def run_feedback_tui():
                    from utim_cli.tui.feedback_dialog import _dialog_submit_feedback_conditional
                    _dialog_submit_feedback_conditional(orchestrator)
                _run_in_terminal_safe(run_feedback_tui)

        threading.Thread(target=_run_queue, daemon=True).start()

    @kb.add('enter')
    def _on_enter(event):
        if _confirm_active[0]:
            return
        buf = input_field.buffer

        # ── If completion menu is open, accept completion and close menu ──
        if buf.complete_state is not None:
            comp = buf.complete_state.current_completion
            if comp is None and buf.complete_state.completions:
                comp = buf.complete_state.completions[0]
            if comp is not None:
                buf.apply_completion(comp)
            buf.cancel_completion()  # properly closes dropdown UI
            return  # close only

        _submit_current_text(event)

    @kb.add('escape', 'enter')
    def _on_newline(event):
        if _confirm_active[0]:
            return
        event.current_buffer.insert_text("\n")

    def _get_line_content():
        try:
            width = shutil.get_terminal_size().columns
        except Exception:
            width = 80
        return [('class:dim', '─' * max(1, width))]

    layout = Layout(
        FloatContainer(
            content=HSplit([
                # NORMAL CHAT VIEW
                ConditionalContainer(
                    content=HSplit([
                        ConditionalContainer(
                            content=Window(
                                content=FormattedTextControl(_get_shell_panel_content, focusable=False),
                                style='class:shell-panel',
                                height=lambda: min(len(_SHELL["output_lines"]) + 2, 14),
                                dont_extend_height=True,
                            ),
                            filter=Condition(lambda: _SHELL["active"]),
                        ),
                        Window(
                            height=lambda: (len(STATE.get("queue", [])) + 4) if (STATE.get("busy") and STATE.get("queue")) else (2 if STATE.get("busy") else 0),
                            content=FormattedTextControl(_get_chat_thinking, focusable=False),
                            dont_extend_height=True,
                        ),
                        VSplit([
                            Window(
                                content=FormattedTextControl(_get_status_bar_left, focusable=False),
                                dont_extend_height=True,
                                height=1,
                                align=WindowAlign.LEFT,
                            ),
                            Window(
                                content=FormattedTextControl(_get_status_bar_right, focusable=False),
                                dont_extend_height=True,
                                height=1,
                                align=WindowAlign.RIGHT,
                            ),
                        ], style='class:status-bar'),
                        input_field,
                        Window(
                            content=FormattedTextControl(_get_line_content, focusable=False),
                            dont_extend_height=True,
                            height=1,
                            wrap_lines=False,
                        ),
                        HSplit([

                            VSplit([
                                Window(
                                    content=FormattedTextControl(_get_footer_line1_left, focusable=False),
                                    dont_extend_height=True,
                                    height=1,
                                    align=WindowAlign.LEFT,
                                ),
                                Window(
                                    content=FormattedTextControl(_get_footer_line1_right, focusable=False),
                                    dont_extend_height=True,
                                    height=1,
                                    align=WindowAlign.RIGHT,
                                ),
                            ]),
                            VSplit([
                                Window(
                                    content=FormattedTextControl(_get_footer_line2_left, focusable=False),
                                    dont_extend_height=True,
                                    height=1,
                                    align=WindowAlign.LEFT,
                                ),
                                Window(
                                    content=FormattedTextControl(_get_footer_line2_right, focusable=False),
                                    dont_extend_height=True,
                                    height=1,
                                    align=WindowAlign.RIGHT,
                                ),
                            ]),
                        ], style='class:footer'),
                    ]),
                    filter=Condition(lambda: not STATE.get("tool_view", {}).get("active"))
                ),
                # FULL SCREEN TOOL VIEWER
                ConditionalContainer(
                    content=Frame(
                        body=tool_view_area,
                        title=lambda: f" Tool Results ({STATE['tool_view']['index'] + 1}/{max(1, len(getattr(orchestrator, 'tool_results', [])))}) - Ctrl+Up/Down to navigate tools - Ctrl+O to exit ",
                        style="class:tool-viewer-frame"
                    ),
                    filter=Condition(lambda: STATE.get("tool_view", {}).get("active"))
                )
            ]),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=ConditionalContainer(
                        content=CompletionsMenu(max_height=8, scroll_offset=2),
                        filter=Condition(lambda: input_field.buffer.complete_state is not None),
                    ),
                ),
            ],
        ),
        focused_element=input_field,
    )

    # Register app with shell module so output reader can call invalidate()
    import utim_cli.tools as _tools_mod
    _tools_mod._SHELL_STATE["_app_ref"] = [None]   # reset; filled below

    pt_app = Application(
        layout=layout,
        style=PT_STYLE,
        key_bindings=kb,
        full_screen=False,
        mouse_support=False,
        erase_when_done=True,
        terminal_size_polling_interval=0.5,  # don't spam redraws during window drag
        # No refresh_interval — screen is static when idle, so Termux scrollback works.
        # The spinner thread below handles animation while busy.
    )
    # Store app reference so _manual_confirm can find it
    _pt_app_ref[0] = pt_app
    _register_app_with_shell(pt_app)   # wire live-output invalidate

    # No resize patch — prompt_toolkit handles resize natively via _last_size tracking.
    # All previous custom erase patches caused more artifacts than they fixed.
    # The UI renders at the bottom of the terminal scrollback; shrinking the window
    # vertically scrolls the terminal emulator, which is expected terminal behaviour.

    # ── Conditional spinner thread ──────────────────────────────────────────
    # Only redraws while the agent is busy (STATE["busy"] == True) or a shell
    # command is active.  When idle the screen is completely static, which
    # lets Termux's two-finger-swipe scrollback work without interference.
    _spinner_stop = threading.Event()

    def _spinner_loop():
        import time as _time
        while not _spinner_stop.is_set():
            # Pause redraws while a confirmation dialog is showing so the
            # arrow-key menu panel isn't overwritten by the status bar.
            if not _confirm_active[0] and (STATE.get("busy") or _SHELL.get("active")):
                try:
                    if pt_app.renderer and not getattr(pt_app.renderer, "waiting_for_cpr", False):
                        pt_app.invalidate()
                except Exception:
                    pass
            _time.sleep(0.12)   # ~8 fps while busy, zero cost when idle

    _spinner_thread = threading.Thread(target=_spinner_loop, daemon=True, name="utim-spinner")
    _spinner_thread.start()


    # Wire manual-confirm callback to orchestrator based on current mode
    def _get_confirm_fn():
        import utim_cli.tools as _t
        if STATE["mode"] != "auto-accept edits":
            return _manual_confirm
        else:
            # Under auto-accept edits, we automatically allow file edits (returning "allow"),
            # but we still want to prompt for run_command using the styled _manual_confirm panel.
            def _auto_accept_confirm(tool_name: str, arguments: dict, diff_lines: list = None) -> str:
                if tool_name == "run_command":
                    if _t._SANDBOX_MODE:
                        # In sandbox mode, auto-allow safe commands, only confirm unsafe ones
                        cmds = []
                        cmd = arguments.get("command")
                        if cmd:
                            cmds.append(cmd)
                        c_list = arguments.get("commands")
                        if c_list and isinstance(c_list, list):
                            cmds.extend(c_list)
                        
                        for c in cmds:
                            is_safe, reason = _t.analyze_command_safety(c)
                            if not is_safe:
                                mod_args = arguments.copy()
                                mod_args["command"] = c
                                if "commands" in mod_args:
                                    del mod_args["commands"]
                                return _manual_confirm(tool_name, mod_args, diff_lines)
                        return "allow"
                    else:
                        # Sandbox disabled: always confirm run_command
                        return _manual_confirm(tool_name, arguments, diff_lines)
                return "allow"
            return _auto_accept_confirm

    orchestrator._get_confirm_fn = _get_confirm_fn

    if initial_prompt:
        def _on_startup_auto_submit():
            text = str(initial_prompt).strip()
            if not text:
                return
            is_logged_in = bool(config.token and config.email and config.email.upper() != "GUEST")
            if not is_logged_in:
                console.print("\n  [bold red]✗ Authentication Required.[/bold red] You must log in before sending a prompt.")
                def run_auth_login():
                    try:
                        import utim_cli.auth as auth
                        auth.login(restart=True)
                    except Exception as exc:
                        console.print(f"\n  [bold red]✗ Login failed: {exc}[/bold red]\n")
                _run_in_terminal_safe(run_auth_login)
                input_field.text = text
                return

            if not _prompt_history or _prompt_history[-1] != text:
                _prompt_history.append(text)

            lines = text.splitlines()
            if len(lines) > 15 or len(text) > 1000:
                line_count = len(lines)
                char_count = len(text)
                _echo_line = f"[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] [Pasted Text: {line_count} lines, {char_count} chars]\n{escape(text[:200])}{'...' if len(text) > 200 else ''}"
            else:
                _echo_line = f"[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] {escape(text)}"

            def _start_task():
                console.print(_echo_line)
                console.print()

            _run_in_terminal_safe(_start_task)

            STATE["busy"] = True
            STATE["busy_start"] = time.time()
            _next_tip()
            pt_app.invalidate()

            STATE["_task_gen"] = STATE.get("_task_gen", 0) + 1
            my_gen = STATE["_task_gen"]

            def _run_queue():
                current_text = text
                while current_text:
                    if STATE.get("_task_gen", my_gen) != my_gen:
                        return
                    try:
                        orchestrator.run_task(current_text)
                    except Exception as e:
                        import traceback
                        console.print(f"\n[bold red]Task Execution Error: {e}[/bold red]")
                        console.print(traceback.format_exc())

                    if STATE.get("_task_gen", my_gen) != my_gen:
                        return

                    queue = STATE.get("queue", [])
                    if queue:
                        current_text = queue.pop(0)
                        console.print(f"\n[bold #42bcf5]{PROMPT_SYMBOL}[/bold #42bcf5] {escape(current_text)}")
                        console.print()
                        STATE["busy_start"] = time.time()
                    else:
                        current_text = None

                if STATE.get("_task_gen", my_gen) == my_gen:
                    STATE["busy"] = False
                    try:
                        pt_app.invalidate()
                    except Exception:
                        pass

            t = threading.Thread(target=_run_queue, daemon=True, name="utim-task-runner")
            t.start()

        def _auto_submit_launcher():
            import time as _t_time
            _t_time.sleep(0.12)
            _on_startup_auto_submit()

        threading.Thread(target=_auto_submit_launcher, daemon=True, name="utim-auto-submit").start()

    return pt_app, input_field


def check_and_update_background():
    """Check npm registry for a newer version of utim-cli and install it silently.
    Respects the auto_update_enabled config flag (default: False).
    Updates via both `pip install --upgrade utim-cli` and `npm install -g @emend-ai/utim@latest`.
    """
    from utim_cli.config import config
    # Respect user preference — default OFF
    if config.get("auto_update_enabled", False) is False:
        return

    def _run():
        try:
            import requests
            import subprocess
            import sys

            # Check npm registry for latest version (faster than PyPI for npm-first installs)
            resp = requests.get(
                "https://registry.npmjs.org/@emend-ai/utim/latest",
                timeout=6,
                headers={"Accept": "application/json"}
            )
            if resp.status_code != 200:
                return

            latest_ver = resp.json().get("version", "")
            current_ver = "2.2.1"

            def parse_ver(v):
                return [int(x) for x in v.split(".") if x.isdigit()]

            if not latest_ver or parse_ver(latest_ver) <= parse_ver(current_ver):
                return  # Already up to date

            is_win = sys.platform == "win32"

            # 1. Update the Python engine via pip (works even without npm)
            pip_proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "utim-cli"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            pip_proc.wait()

            # 2. Also update the npm wrapper so `utim` stays in sync
            npm_proc = subprocess.Popen(
                "npm install -g @emend-ai/utim@latest",
                shell=is_win,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            npm_proc.wait()

            # Flag so startup banner shows the update notice next launch
            if pip_proc.returncode == 0:
                config.set("background_updated_version", latest_ver)

        except Exception:
            pass

    import threading
    t = threading.Thread(target=_run, daemon=True, name="utim-autoupdate")
    t.start()


from utim_cli.tui.update_dialog import _dialog_auto_update

def start_chat(initial_prompt: Optional[str] = None):
    orchestrator = Orchestrator(console)

    # ── Background Quota Poller to detect Pay As You Go top-ups ────────
    def _quota_poller():
        import time
        import requests
        import sys
        import os
        import threading
        from utim_cli.config import config
        from utim_cli.auth import SERVER_URL

        while True:
            time.sleep(90)

            api_key = config.get("api_key")
            if not api_key:
                continue
            try:
                resp = requests.get(
                    f"{SERVER_URL}/api/usage",
                    headers={"X-API-Key": api_key},
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    is_subscribed = data.get("is_subscribed", False)
                    if not is_subscribed:
                        bonus_balance = data.get("bonus_balance", 0.0)
                        if last_bonus is not None and bonus_balance > last_bonus:
                            added = bonus_balance - last_bonus
                            config.set("bonus_credits_pending_message", str(added))
                            os.execv(sys.executable, [sys.executable] + sys.argv)
                        last_bonus = bonus_balance
            except Exception:
                pass

    import threading
    _poller_thread = threading.Thread(target=_quota_poller, daemon=True, name="utim-quota-poller")
    _poller_thread.start()

    # ── Check if updated in background previously ──────────────────────
    from utim_cli.config import config
    updated_ver = config.get("background_updated_version")
    if updated_ver:
        config.set("background_updated_version", None)  # clear flag
        console.print(
            f"\n  [bold green]✦ Notice: UTIM CLI has been successfully updated to v{updated_ver} in the background.[/bold green]\n"
        )

    # ── Check if bonus credits were added via Pay As You Go top-up ─────
    bonus_credited = config.get("bonus_credits_pending_message")
    if bonus_credited:
        config.set("bonus_credits_pending_message", None)  # clear flag
        try:
            amount_usd = float(bonus_credited) / 1000.0
            console.print()
            console.print(
                f"  [bold #e5ff00]✦ Yay!! Bonus Quota of {int(float(bonus_credited))} credits (${amount_usd:.2f}) Credited Let's Go Build! [/bold #e5ff00]"
            )
            console.print(
                f"  [bold green]Premium models are now unlocked while your bonus lasts.[/bold green]\n"
            )
        except Exception:
            pass

    # ── Load session state if it exists ──────────────────────────────────
    import json
    from utim_cli.config import get_utim_dir as _get_utim_dir
    _ud = _get_utim_dir()
    state_file = _ud / "session_state.json"
    session_restored = False
    if config.get("restore_session_state", True) and os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            
            orchestrator.session_id = saved.get("session_id")
            orchestrator.messages = saved.get("messages", [])
            orchestrator.turn_history = saved.get("turn_history", [])
            orchestrator.redo_history = saved.get("redo_history", [])
            if "model_id" in saved:
                orchestrator.model_id = saved["model_id"]
            if "model_source" in saved:
                orchestrator.model_source = saved["model_source"]
                
            STATE["session_id"] = saved.get("session_id")
            if "queue" in saved:
                STATE["queue"] = saved["queue"]
            
            # Derive topic for display
            first_user = next(
                (m.get("content", "") or "" for m in orchestrator.messages if m.get("role") == "user"),
                "",
            )
            if first_user:
                if isinstance(first_user, list):
                    first_user = " ".join(p.get("text", "") for p in first_user if isinstance(p, dict))
                STATE['session_topic'] = first_user[:40]
            
            session_restored = True
        except Exception as e:
            console.print(f"[dim yellow]Warning: Could not load saved session state: {e}[/dim yellow]\n")

    if not session_restored:
        usage_file = _ud / "session_usage.json"
        if os.path.exists(usage_file):
            try:
                os.remove(usage_file)
            except Exception:
                pass

    # Print startup banner ONCE before entering the loop
    _print_animated_banner()

    # Start background version check and update loop
    check_and_update_background()

    # ── Eager Hugging Face model warm-up (background, instant cache) ──────────
    # Download/load all-MiniLM-L6-v2 immediately at startup so the first task
    # never blocks waiting for the model. Runs silently in a daemon thread.
    def _warmup_hf_model():
        try:
            from utim_cli.vector_memory import warmup_embedding_model
            warmup_embedding_model()
        except Exception:
            pass

    _warmup_thread = threading.Thread(target=_warmup_hf_model, daemon=True, name="utim-hf-warmup")
    _warmup_thread.start()

    if session_restored:
        console.print(f"  [bold green]✓ Restored active session state from {state_file}[/bold green]")
        console.print("  [dim]To turn of active session restore use \"/chatrestore\"[/dim]\n")
        _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))

    _last_sigint = [0.0]
    pending_prompt = [initial_prompt] if initial_prompt else []

    while True:   # restart loop — re-enters after dialog commands
        prompt_to_pass = pending_prompt.pop(0) if pending_prompt else None
        pt_app, input_field = _build_pt_app(orchestrator, _last_sigint, initial_prompt=prompt_to_pass)

        # Fallback SIGINT handler — fires when a dialog app is running (not pt_app).
        # The main Ctrl+C double-press-to-exit logic lives in the 'c-c' key binding
        # inside _build_pt_app, which is immune to prompt_toolkit signal restoration.
        def _sigint_handler(signum, frame):
            now = time.time()
            double_press = (now - _last_sigint[0]) < 1.0
            _last_sigint[0] = now
            STATE["last_ctrl_c"] = now
            # Shell focused: Ctrl+C is for the child process, not the agent
            if _SHELL["active"] and _SHELL["focused"]:
                return
            if double_press:
                sys.stdout.write("\n\033[1;34mGoodbye! See you next time.\033[0m\n\n")
                sys.stdout.flush()
                os._exit(0)
            if STATE["busy"]:
                STATE["queue"] = []
                STATE["busy"] = False
                STATE["thinking_topic"] = ""
                # Bump generation so the active _run_queue thread self-exits immediately
                STATE["_task_gen"] = STATE.get("_task_gen", 0) + 1
                orchestrator.abort()
                
                # Send cancel request to the server in a daemon thread so it doesn't block the UI
                import threading
                def send_cancel_to_server():
                    try:
                        import requests
                        from utim_cli.auth import SERVER_URL
                        from utim_cli.config import config
                        session_id = getattr(orchestrator, "session_id", None)
                        api_key = config.get("api_key")
                        if api_key:
                            headers = {
                                "X-API-Key": api_key,
                                "Content-Type": "application/json"
                            }
                            requests.post(
                                f"{SERVER_URL}/completions/cancel",
                                json={"session_id": session_id},
                                headers=headers,
                                timeout=5
                            )
                    except Exception:
                        pass
                threading.Thread(target=send_cancel_to_server, daemon=True).start()

                sys.stdout.write("\n\033[33m⊘  Aborted.\033[0m\n")
                sys.stdout.flush()
            else:
                sys.stdout.write("\n\033[2m(Press Ctrl+C again to exit)\033[0m\n")
                sys.stdout.flush()

        signal.signal(signal.SIGINT, _sigint_handler)

        with patch_stdout(raw=True):
            # Eagerly capture the event loop so background threads (e.g. _run_queue Thread-2)
            # always find _MAIN_LOOP set when they call _run_in_terminal_safe.
            import asyncio as _asyncio
            global _MAIN_LOOP
            try:
                _MAIN_LOOP = _asyncio.get_event_loop()
            except Exception:
                pass
            result = pt_app.run()

        if result == 'model':
            _dialog_model(orchestrator)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'modelsettings':
            _dialog_modelsettings(orchestrator)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'tools':
            _dialog_tools(orchestrator)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'mcp':
            _dialog_mcp(orchestrator)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'resume':
            loaded = _dialog_resume(orchestrator)
            if loaded:  # None means the user cancelled the dialog
                _clear_terminal_screen()
                _print_animated_banner(animated=False)
                _print_session_history(orchestrator, loaded, STATE.get('session_topic', ''))
                orchestrator._persist_messages()
            else:
                _clear_terminal_screen()
                _print_animated_banner(animated=False)
                _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'rewind':
            _dialog_rewind(orchestrator)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'undo':
            args = STATE.pop("command_args", [])
            _action_undo(orchestrator, args)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        elif result == 'redo':
            args = STATE.pop("command_args", [])
            _action_redo(orchestrator, args)
            _clear_terminal_screen()
            _print_animated_banner(animated=False)
            _print_session_history(orchestrator, orchestrator.messages, STATE.get('session_topic', ''))
            # loop back → restart app
        else:
            # Normal exit (quit command or double Ctrl+C)
            signal.signal(signal.SIGINT, signal.SIG_DFL)
            os._exit(0)



# ─── Typer entry-point ────────────────────────────────────────────────────────
app = typer.Typer()

def version_callback(value: bool):
    if value:
        import typer
        from utim_cli import __version__
        print(f"UTIM CLI v{__version__} — U Think I Make")
        raise typer.Exit()


def run_headless_task(
    prompt: str,
    sandbox: bool = False,
    sandbox_image: str = "ubuntu:22.04",
    model: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """Run a task instruction non-interactively in headless mode for benchmark evaluation harnesses like Harbor / Terminal-Bench."""
    import sys
    import os

    # Force headless flag in environment
    os.environ["UTIM_HEADLESS"] = "1"

    # Automatically initialize .utim on startup
    try:
        from utim_cli.bootstrap import initialize_utim
        initialize_utim()
    except Exception:
        pass

    from utim_cli.config import config
    import utim_cli.tools as _t

    is_dry_run = dry_run or config.dry_run
    if is_dry_run:
        _t._DRY_RUN = True

    if sandbox:
        _t._SANDBOX_MODE = True
        _t._SANDBOX_IMAGE = sandbox_image

    orchestrator = Orchestrator(console)
    if model:
        orchestrator.model_id = model

    # In headless mode, tool executions are auto-accepted without interactive user confirmation prompts
    orchestrator._get_confirm_fn = lambda: (lambda tool_name, arguments, diff_lines=None: "allow")

    # Check authentication / API key availability
    api_key = config.get("api_key") or getattr(orchestrator, "_local_api_key", None)
    if not api_key:
        console.print(
            "\n  [bold red]✗ Authentication Required.[/bold red] "
            "Please log in (`utim login`) or set UTIM_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY environment variable for headless execution.\n"
        )
        return 1

    # Eager Hugging Face model warm-up (silent background)
    try:
        from utim_cli.vector_memory import warmup_embedding_model
        warmup_embedding_model()
    except Exception:
        pass

    try:
        orchestrator.run_task(prompt)
        return 0
    except Exception as exc:
        console.print(f"\n  [bold red]✗ Headless task failed: {exc}[/bold red]\n")
        return 1


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    sandbox: bool = typer.Option(
        False,
        "--sandbox/--no-sandbox",
        help=(
            "Enable intelligent sandboxing for terminal commands. "
            "Risky commands will be blocked or require confirmation."
        ),
    ),
    sandbox_image: str = typer.Option(
        "ubuntu:22.04",
        "--sandbox-image",
        help="[Legacy] Maintenance parameter (unused in intelligent host sandboxing).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run in dry-run mode (simulate file changes and commands without mutating).",
    ),
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
    ssl_verify: bool = typer.Option(
        None,
        "--ssl-verify/--no-ssl-verify",
        help="Enable/disable SSL certificate validation for server requests.",
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Run in non-interactive headless mode for harbor agent and benchmark suites.",
    ),
    prompt: Optional[str] = typer.Option(
        None,
        "-p",
        "--prompt",
        help="Task prompt for headless single-shot task execution.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "-m",
        "--model",
        help="Model ID to use for the task execution.",
    ),
):
    # Automatically initialize .utim on startup
    try:
        from utim_cli.bootstrap import initialize_utim
        initialize_utim()
    except Exception:
        pass

    from utim_cli.config import config

    if ssl_verify is not None:
        config.set("verify_ssl", ssl_verify)
        from utim_cli.config import _apply_ssl_session_patch
        _apply_ssl_session_patch(disable=not ssl_verify)

    is_dry_run = dry_run or config.dry_run

    if is_dry_run:
        import utim_cli.tools as _t
        _t._DRY_RUN = True
        console.print(
            "\n  [bold yellow]⬡  Dry-Run Mode active[/bold yellow] "
            "[dim](Edits and command executions will be simulated)[/dim]\n"
        )

    if ctx.invoked_subcommand is None:
        is_headless = headless or os.getenv("UTIM_HEADLESS") == "1" or os.getenv("HEADLESS") == "1"
        
        # Read from stdin if non-interactive TTY or headless and prompt not explicitly provided
        if not prompt and not sys.stdin.isatty():
            try:
                stdin_text = sys.stdin.read().strip()
                if stdin_text:
                    prompt = stdin_text
                    is_headless = True
            except Exception:
                pass

        if is_headless:
            if not prompt:
                console.print("\n  [bold red]✗ Error: No prompt provided for headless execution.[/bold red]")
                console.print("  [dim]Provide a prompt via -p/--prompt, 'utim task --headless ...', 'utim run ...', or pipe text into stdin.[/dim]\n")
                raise typer.Exit(code=1)
            code = run_headless_task(prompt, sandbox=sandbox, sandbox_image=sandbox_image, model=model, dry_run=is_dry_run)
            raise typer.Exit(code=code)

        if sandbox:
            import utim_cli.tools as _t
            _t._SANDBOX_MODE  = True
            _t._SANDBOX_IMAGE = sandbox_image
            console.print(
                "\n  [bold #a6e3a1]⬡  Intelligent Sandbox active[/bold #a6e3a1] "
                "[dim](Risky terminal commands will require manual confirmation)[/dim]\n"
            )
        start_chat()

@app.command()
def task(
    prompt: str,
    sandbox: bool = typer.Option(
        False,
        "--sandbox/--no-sandbox",
        help=(
            "Enable intelligent sandboxing for terminal commands. "
            "Risky commands will be blocked."
        ),
    ),
    sandbox_image: str = typer.Option(
        "ubuntu:22.04",
        "--sandbox-image",
        help="[Legacy] Maintenance parameter (unused in intelligent host sandboxing).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run in dry-run mode (simulate file changes and commands without mutating).",
    ),
    ssl_verify: bool = typer.Option(
        None,
        "--ssl-verify/--no-ssl-verify",
        help="Enable/disable SSL certificate validation for server requests.",
    ),
    headless: bool = typer.Option(
        False,
        "--headless",
        help="Run in non-interactive headless mode for harbor agent and benchmark suites.",
    ),
    model: Optional[str] = typer.Option(
        None,
        "-m",
        "--model",
        help="Model ID to use for the task execution.",
    ),
):
    # Automatically initialize .utim on startup
    try:
        from utim_cli.bootstrap import initialize_utim
        initialize_utim()
    except Exception:
        pass

    from utim_cli.config import config

    if ssl_verify is not None:
        config.set("verify_ssl", ssl_verify)
        from utim_cli.config import _apply_ssl_session_patch
        _apply_ssl_session_patch(disable=not ssl_verify)

    is_headless = headless or os.getenv("UTIM_HEADLESS") == "1" or os.getenv("HEADLESS") == "1" or not sys.stdin.isatty()

    if is_headless:
        code = run_headless_task(prompt, sandbox=sandbox, sandbox_image=sandbox_image, model=model, dry_run=dry_run or config.dry_run)
        raise typer.Exit(code=code)

    # Require login before executing task in interactive mode
    is_logged_in = bool(config.token and config.email and config.email.upper() != "GUEST")
    if not is_logged_in:
        console.print("\n  [bold red]✗ Authentication Required.[/bold red] You must log in before sending a prompt.")
        try:
            import utim_cli.auth as auth
            auth.login()
        except Exception as exc:
            console.print(f"\n  [bold red]✗ Login failed: {exc}[/bold red]\n")
            raise typer.Exit(code=1)

    is_dry_run = dry_run or config.dry_run

    if is_dry_run:
        import utim_cli.tools as _t
        _t._DRY_RUN = True
        c = Console()
        c.print(
            "\n  [bold yellow]⬡  Dry-Run Mode active[/bold yellow] "
            "[dim](Edits and command executions will be simulated)[/dim]\n"
        )

    if sandbox:
        import utim_cli.tools as _t
        _t._SANDBOX_MODE  = True
        _t._SANDBOX_IMAGE = sandbox_image
    
    start_chat(initial_prompt=prompt)

@app.command("run")
def run_cmd(
    prompt: Optional[str] = typer.Argument(None, help="The prompt or task instruction to execute."),
    headless: bool = typer.Option(
        True,
        "--headless/--interactive",
        help="Run in non-interactive headless mode (default: True for 'run').",
    ),
    sandbox: bool = typer.Option(
        False,
        "--sandbox/--no-sandbox",
        help="Enable intelligent sandboxing for terminal commands.",
    ),
    sandbox_image: str = typer.Option("ubuntu:22.04", "--sandbox-image"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    model: Optional[str] = typer.Option(None, "-m", "--model", help="Model ID to use for task execution."),
):
    """Run a single task instruction non-interactively in headless mode (ideal for Harbor / Terminal-Bench)."""
    # Auto-initialize workspace
    try:
        from utim_cli.bootstrap import initialize_utim
        initialize_utim()
    except Exception:
        pass

    if not prompt and not sys.stdin.isatty():
        try:
            prompt = sys.stdin.read().strip()
        except Exception:
            prompt = None

    if not prompt:
        console.print("\n  [bold red]✗ Error: Prompt is required for 'run' command.[/bold red]\n")
        raise typer.Exit(code=1)

    is_headless = headless or os.getenv("UTIM_HEADLESS") == "1" or os.getenv("HEADLESS") == "1" or not sys.stdin.isatty()

    if is_headless:
        code = run_headless_task(prompt, sandbox=sandbox, sandbox_image=sandbox_image, model=model, dry_run=dry_run)
        raise typer.Exit(code=code)
    else:
        start_chat(initial_prompt=prompt)

@app.command()
def doctor():
    """Run system, environment, and MCP connectivity diagnostics."""
    from utim_cli.doctor import run_diagnostics
    run_diagnostics(console)

@app.command()
def init():
    """Initialize the UTIM local intelligence database and configuration workspace."""
    from utim_cli.bootstrap import initialize_utim
    console.print("\n  [bold #42bcf5]Initializing UTIM workspace...[/bold #42bcf5]")
    try:
        db_path = initialize_utim()
        console.print(f"  [bold green]✓ UTIM Workspace initialized successfully.[/bold green]")
        console.print(f"  Intelligence DB: [bold white]{db_path}[/bold white]\n")
    except Exception as e:
        console.print(f"  [bold red]✗ Failed to initialize workspace: {e}[/bold red]\n")
        raise typer.Exit(code=1)

@app.command()
def reset():
    """Clear workspace .utim cache and local state safely (backups are preserved)."""
    import shutil
    from utim_cli.config import get_utim_dir
    confirm = typer.confirm("Are you sure you want to reset your local .utim workspace cache? This will clear local memory and experiences.")
    if confirm:
        utim_dir = get_utim_dir()
        if utim_dir.exists():
            try:
                try:
                    from utim_cli.local_db import close_local_db
                    close_local_db()
                except Exception as err:
                    print(f"[DEBUG] close_local_db failed: {err}", flush=True)
                try:
                    from utim_cli.server.history import close_history_db
                    close_history_db()
                except Exception as err:
                    print(f"[DEBUG] close_history_db failed: {err}", flush=True)
                shutil.rmtree(utim_dir)
                console.print("  [bold green]✓ Local .utim workspace cache cleared successfully.[/bold green]\n")
            except Exception as e:
                console.print(f"  [bold red]✗ Failed to clear .utim workspace cache: {e}[/bold red]\n")
                raise typer.Exit(code=1)
        else:
            console.print("  [yellow]No .utim cache directory found to clear.[/yellow]\n")


@app.command()
def usage():
    """Show your quota usage percentage and 5-hour refill details."""
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests

    api_key = config.get("api_key")
    if not api_key:
        console.print("  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
        raise typer.Exit(code=1)

    try:
        resp = requests.get(
            f"{SERVER_URL}/api/usage",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        console.print(f"  [bold red]✗ Failed to fetch usage from server: {exc}[/bold red]\n")
        raise typer.Exit(code=1)

    render_usage_menu(data)


@app.command()
def quota():
    """Show your monthly UTIM credit quota and plan details."""
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests
    from rich.panel import Panel

    api_key = config.get("api_key")
    if not api_key:
        console.print("  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
        raise typer.Exit(code=1)

    try:
        resp = requests.get(
            f"{SERVER_URL}/quota",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        q = resp.json()
    except Exception as exc:
        console.print(f"  [bold red]✗ Failed to fetch quota information from server: {exc}[/bold red]\n")
        raise typer.Exit(code=1)

    used = q.get("credits_used", q.get("requests_used", 0.0))
    limit = q.get("credits_limit", q.get("requests_limit", 1000))
    percent = q["percent_used"]

    bar_width = 20
    filled = int(round((used / limit) * bar_width)) if limit > 0 else 0
    filled = min(bar_width, max(0, filled))
    bar = "█" * filled + "░" * (bar_width - filled)

    bar_color = "red" if percent >= 90 else ("yellow" if percent >= 75 else "green")

    used_usd = used / 1000.0
    limit_usd = limit / 1000.0

    content = (
        f"  Plan:     [bold cyan]{q['display_name']}[/bold cyan] ([dim]{q['plan']}[/dim])\n"
        f"  Usage:    [bold {bar_color}]{bar}[/bold {bar_color}]  {used:,.1f} / {limit:,} credits ({percent}%)\n"
    )

    # Separate row for Bonus Credits if configured
    bonus_limit = q.get("free_bonus_limit") or 0.0
    if bonus_limit > 0.0:
        bonus_bal = q.get("free_bonus_balance") or 0.0
        bonus_used = max(0.0, bonus_limit - bonus_bal)
        bonus_pct = round((bonus_used / bonus_limit) * 100, 1) if bonus_limit > 0 else 0.0
        b_filled = int(round((bonus_used / bonus_limit) * bar_width)) if bonus_limit > 0 else 0
        b_filled = min(bar_width, max(0, b_filled))
        b_bar = "█" * b_filled + "░" * (bar_width - b_filled)
        b_color = "red" if bonus_pct >= 90 else ("yellow" if bonus_pct >= 75 else "green")
        content += f"  Bonus:    [bold {b_color}]{b_bar}[/bold {b_color}]  {bonus_used:,.1f} / {bonus_limit:,} credits ({bonus_pct}%)\n"

    content += (
        f"  Value:    [bold green]${used_usd:.2f}[/bold green] / [bold green]${limit_usd:.2f}[/bold green] USD [dim](1,000 credits = $1)[/dim]\n"
        f"  Resets:   in [bold cyan]{q['days_until_reset']}[/bold cyan] days  ([dim]{q['reset_at'][:10]}[/dim])\n\n"
        f"  [dim]Tip: Upgrade your plan for higher limits and premium models[/dim] → [bold]utim upgrade[/bold]"
    )

    panel = Panel(
        content,
        title="[bold white]UTIM Quota[/bold white]",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


@app.command()
def upgrade():
    """Upgrade your UTIM plan (opens Razorpay checkout in your browser)."""
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests
    import webbrowser
    import locale
    import time

    api_key = config.get("api_key")
    if not api_key:
        console.print("  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
        raise typer.Exit(code=1)

    # Detect user location/currency preference
    is_indian = False
    try:
        loc = locale.getdefaultlocale()
        if loc and loc[0] and loc[0].upper().endswith("IN"):
            is_indian = True
        tz = time.tzname
        if tz and any("IST" in t or "India" in t for t in tz):
            is_indian = True
    except Exception:
        pass

    currency = "INR" if is_indian else "USD"

    if is_indian:
        hobby_price = "₹700"
        pro_price = "₹2500"
        team_price = "₹3500"
        ent_price = "₹5000"
    else:
        hobby_price = "$7.00"
        pro_price = "$25.00"
        team_price = "$35.00"
        ent_price = "$50.00"

    console.print("\n  [bold cyan]Available Tiers to Subscribe/Upgrade:[/bold cyan]")
    console.print(f"  [bold]1[/bold] - Hobby Plan      — {hobby_price}/mo (4,000 credits / +500 bonus on first purchase)")
    console.print(f"  [bold]2[/bold] - Pro Plan        — {pro_price}/mo (18,000 credits / +2,000 bonus on first purchase)")
    console.print(f"  [bold]3[/bold] - Team Plan       — {team_price}/mo (45,000 credits)")
    console.print(f"  [bold]4[/bold] - Enterprise Plan — {ent_price}/mo (80,000 credits)")
    console.print("  [bold]5[/bold] - Cancel")

    choice = typer.prompt("\n  Select an option (1-5)", default="5")
    if choice == "1":
        plan_id = "hobby"
    elif choice == "2":
        plan_id = "pro"
    elif choice == "3":
        plan_id = "team"
    elif choice == "4":
        plan_id = "enterprise"
    else:
        console.print("  [yellow]Upgrade cancelled.[/yellow]\n")
        return

    spinner_type = "line" if (_IS_LEGACY_WIN or getattr(sys.stdout, 'encoding', '').lower() not in ('utf-8', 'utf8', 'cp65001')) else "dots"
    with console.status("[bold green]Creating subscription link...", spinner=spinner_type):
        try:
            resp = requests.post(
                f"{SERVER_URL}/subscribe",
                json={
                    "plan_id": plan_id,
                    "currency": currency
                },
                headers={"X-API-Key": api_key},
                timeout=10,
            )
            resp.raise_for_status()
            checkout_url = resp.json()["checkout_url"]
        except Exception as exc:
            console.print(f"\n  [bold red]✗ Failed to create subscription checkout: {exc}[/bold red]\n")
            raise typer.Exit(code=1)

    console.print(f"\n  [bold green]✓ Subscription link generated successfully![/bold green]")
    console.print(f"  Opening browser to: [cyan]{checkout_url}[/cyan]\n")
    webbrowser.open(checkout_url)


@app.command()
def billing():
    """Show details of your active UTIM billing profile."""
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests
    from rich.panel import Panel

    api_key = config.get("api_key")
    if not api_key:
        console.print("  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
        raise typer.Exit(code=1)

    try:
        resp = requests.get(
            f"{SERVER_URL}/quota",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        q = resp.json()
    except Exception as exc:
        console.print(f"  [bold red]✗ Failed to fetch billing status from server: {exc}[/bold red]\n")
        raise typer.Exit(code=1)

    content = (
        f"  Active Plan:         [bold cyan]{q['display_name']}[/bold cyan] ([dim]{q['plan']}[/dim])\n"
        f"  Account Email:       [bold white]{config.get('email', 'N/A')}[/bold white]\n"
        f"  Status:              [bold green]Active[/bold green]\n"
        f"  Current Period End:  [white]{q['reset_at'][:10]} {q['reset_at'][11:19]}[/white]\n"
        f"  Days Remaining:      [bold cyan]{q['days_until_reset']}[/bold cyan] days\n\n"
        f"  [dim]To upgrade or change plans, run[/dim] [bold]utim upgrade[/bold]"
    )

    panel = Panel(
        content,
        title="[bold white]Billing Status[/bold white]",
        border_style="cyan",
        expand=False,
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


@app.command()
def plan():
    """Show available subscription plans and their feature comparison."""
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests
    from rich.table import Table

    api_key = config.get("api_key")
    headers = {"X-API-Key": api_key} if api_key else {}

    try:
        resp = requests.get(
            f"{SERVER_URL}/plans",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        plans = resp.json()
    except Exception as exc:
        console.print(f"  [bold red]✗ Failed to fetch plans comparison: {exc}[/bold red]\n")
        raise typer.Exit(code=1)

    table = Table(title="[bold white]UTIM Subscription Tiers[/bold white]", border_style="cyan")
    table.add_column("Plan", style="cyan", no_wrap=True)
    table.add_column("Price", justify="right", style="green")
    table.add_column("Monthly Limit", justify="right", style="magenta")
    table.add_column("Context Window", justify="right", style="white")
    table.add_column("Allowed Models", style="dim white")

    for p in plans:
        price_str = f"₹{p.get('price_inr', 0):,}/mo"
        credits_val = p.get('credits_per_month', p.get('requests_per_month', 0))
        usd_val = credits_val / 1000.0
        limit_str = f"{credits_val:,} credits (${usd_val:,.2f})"
        context_str = f"{p['max_context_k']}k"
        
        models_str = p['allowed_models']
        if models_str == "free":
            models_str = "Free-tier models only"
        elif models_str == "all":
            models_str = "All models (Premium included)"
        elif "gpt-4o" in models_str:
            models_str = "Free models + GPT-4o"

        table.add_row(
            p['display_name'],
            price_str,
            limit_str,
            context_str,
            models_str
        )

    console.print()
    console.print(table)
    console.print()


@app.command()
def login():
    """Sign in to your UTIM account to authenticate CLI access."""
    from utim_cli.config import config
    import utim_cli.auth as auth

    if config.token:
        console.print(f"\n  [yellow]You are already logged in as [bold]{config.email}[/bold].[/yellow]")
        console.print("  [dim]Run [white]utim logout[/white] first if you want to switch accounts.[/dim]\n")
        return

    try:
        auth.login()
        if config.get("api_key"):
            import os as _os
            _os._exit(0)
        # Fetch user plan immediately after login
        api_key = config.get("api_key")
        user_type = "UTIM Community"
        if api_key:
            try:
                from utim_cli.auth import SERVER_URL
                import requests
                resp = requests.get(
                    f"{SERVER_URL}/api/user-plan",
                    headers={"X-API-Key": api_key},
                    timeout=5.0,
                )
                if resp.ok:
                    plan_name = resp.json().get("plan", "free")
                    config.set("user_plan", plan_name)
                    PLAN_NAME_MAP = {
                        "free": "Free",
                        "hobby": "Hobbyist Node",
                        "pro": "Starter Node",
                        "max": "Professional Core",
                        "ultimate": "MAX Node"
                    }
                    user_type = f"UTIM {PLAN_NAME_MAP.get(plan_name.lower().strip(), plan_name.title())}"
            except Exception:
                pass

        console.print(f"\n  [bold green]✓ Successfully logged in as:[/bold green] [bold white]{config.email}[/bold white]")
        console.print(f"  [dim]{config.email}  •  {user_type}[/dim]\n")
    except Exception as exc:
        console.print(f"\n  [bold red]✗ Login failed: {exc}[/bold red]\n")
        raise typer.Exit(code=1)


@app.command()
def logout():
    """Sign out of your UTIM account and clear local session keys."""
    from utim_cli.config import config

    if not config.token:
        console.print("\n  [dim]You are already logged out.[/dim]\n")
    else:
        config.clear()
        console.print("\n  [bold #f9e2af]✓ Successfully logged out.[/bold #f9e2af]\n")


@app.command("quota-preference")
def set_quota_preference(
    preference: str = typer.Argument(
        ...,
        help="Preferred credit quota to prioritize: 'regular' or 'bonus'."
    )
):
    """Set your preferred credit quota to use for agent completions ('regular' or 'bonus')."""
    pref = preference.lower().strip()
    if pref not in ("regular", "bonus"):
        console.print("  [bold red]✗ Invalid quota preference.[/bold red] Choose either 'regular' or 'bonus'.\n")
        raise typer.Exit(code=1)
    
    from utim_cli.config import config
    config.set("preferred_quota", pref)
    console.print(f"\n  [bold green]✓ Quota preference updated:[/bold green] Prioritizing [bold white]{pref}[/bold white] quota first.\n")


KNOWN_COMMANDS = {
    "task", "run", "version", "doctor", "config", "share", "mcp",
    "skills", "undo", "redo", "rewind", "login", "logout",
    "quota-preference", "help", "--help", "-h", "--version", "-v"
}

def main_cli_entry():
    import sys
    import os
    _entry_script = os.path.basename(sys.argv[0] if sys.argv else "").lower()
    if "utimlite" in _entry_script:
        os.environ["UTIM_LITE_MODE"] = "1"
    if len(sys.argv) == 2:
        first_arg = sys.argv[1].strip()
        if not first_arg.startswith("-") and first_arg.lower() not in KNOWN_COMMANDS and ' ' in first_arg:
            sys.argv.insert(1, "task")
    app()

if __name__ == "__main__":
    main_cli_entry()



