---
name: terminal-ui-design
description: Guidelines and best practices for creating beautiful, responsive terminal UIs (TUIs) in Python using Rich and prompt_toolkit. Activate this skill when designing command-line interfaces, terminal layouts, interactive forms, status displays, or complex console outputs.
---

# Terminal UI (TUI) Design Guide

Terminal UIs must combine aesthetic appeal with technical reliability. This guide outlines how to build professional TUIs using **Rich** (for output formatting, layouts, and panels) and **prompt_toolkit** (for interactive loops, input validation, auto-completion, and keybindings).

---

## 1. Color Palette & Theming (Rich)

Avoid browser-like colors and default console greens/reds. Instead, use a cohesive, modern color palette.

### Recommended Colors (Hex & Standard Names)
- **Primary/Accent**: Cyan (`#00f0ff` or `cyan`), Light Coral (`#ff79c6` or `magenta`)
- **Success**: Bright Green/Emerald (`#50fa7b` or `green`)
- **Warning**: Amber/Orange (`#ffb86c` or `yellow`)
- **Error/Danger**: Pastel Red (`#ff5555` or `red`)
- **Dim/Muted Text**: Grey (`#6272a4` or `grey50` / `dim`)

### Implementation Pattern
Use `rich.theme.Theme` to define a central stylesheet instead of hardcoding style strings:

```python
from rich.theme import Theme
from rich.console import Console

utim_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "danger": "bold red",
    "success": "bold green",
    "header": "bold cyan reverse",
    "muted": "grey50",
    "highlight": "bold magenta"
})

console = Console(theme=utim_theme)
console.print("System initialised successfully.", style="success")
```

---

## 2. Structured Layouts & Grids

For complex outputs, split the terminal screen into logical zones using `Layout` or `Table` from Rich.

### Using `Layout`
For fullscreen TUI representations:
```python
from rich.layout import Layout
from rich.panel import Panel

layout = Layout()
# Split into header, body, footer
layout.split_column(
    Layout(name="header", size=3),
    Layout(name="body"),
    Layout(name="footer", size=3)
)
# Split body horizontally
layout["body"].split_row(
    Layout(name="sidebar", ratio=1),
    Layout(name="main", ratio=3)
)

layout["header"].update(Panel("UTIM CLI Assistant", style="header"))
layout["sidebar"].update(Panel("Navigation\n[dim]- /undo\n- /doctor\n- /report[/dim]"))
layout["main"].update(Panel("Welcome to the workspace!"))
layout["footer"].update(Panel("Press Ctrl+C to exit", style="muted"))
```

### Table Layouts (Grid/Border Options)
Always set clear column widths, padding, and box types. Use `box.ROUNDED` or `box.MINIMAL` for a premium feel:
```python
from rich.table import Table
from rich import box

table = Table(title="Connected MCP Servers", box=box.ROUNDED, show_header=True)
table.add_column("Server Name", style="cyan", no_wrap=True)
table.add_column("Status", style="success")
table.add_column("Tools Loaded", justify="right", style="muted")

table.add_row("github", "Connected", "26")
table.add_row("figma-mcp-server", "[red]Failed[/red]", "0")
```

---

## 3. Interactive Inputs & Prompts (prompt_toolkit)

For multi-line inputs, command suggestions, or tab-navigation, use `prompt_toolkit`.

### Full-Featured Prompt with Autocomplete & Keybindings
```python
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings

# 1. Define autocompleter
command_completer = WordCompleter(
    ['/undo', '/redo', '/rewind', '/doctor', '/report', '/reset'],
    ignore_case=True
)

# 2. Custom Keybindings
bindings = KeyBindings()

@bindings.add('c-m')  # Ctrl+M to launch model picker
def _(event):
    # Triggers model configuration flow
    event.app.exit(result="TRIGGER_MODEL_PICKER")

session = PromptSession(completer=command_completer, key_bindings=bindings)

try:
    user_input = session.prompt("utim > ")
except (KeyboardInterrupt, EOFError):
    user_input = "/exit"
```

---

## 4. Live Updates & Progress Bars

Always show feedback for long-running operations. Never let the terminal freeze.

### Spinning Status Context Manager
For quick async operations (e.g. database querying, server restart):
```python
import time
from rich.console import Console

console = Console()
with console.status("[bold green]Connecting to MCP servers...", spinner="dots"):
    # Perform startup operations
    time.sleep(1.5)
console.print("[success]✓ Connected to github successfully![/success]")
```

### Interactive Progress Bars
For multi-step loops (e.g. processing files, downloading dependencies):
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
) as progress:
    task = progress.add_task("[cyan]Re-indexing codebase...", total=100)
    
    while not progress.finished:
        progress.update(task, advance=10)
        time.sleep(0.1)
```

---

## 5. Screen Clears & Dynamic Redraws

To prevent polluting the terminal scrollback history (e.g. during user confirmations or menus):

1. **Clear current lines**: Use `console.print("\033[F\033[K", end="")` to move up one line and clear it.
2. **Alternate Screen Buffer**: Use `prompt_toolkit.application.Application(full_screen=True)` for full-screen dashboards, which restores the terminal exactly as it was when the program exits.
3. **Live Display**: Use `rich.live.Live` to refresh a specific UI component in-place:
```python
from rich.live import Live
import time

with Live(table, refresh_per_second=4) as live:
    for i in range(10):
        # Mutate table
        table.add_row(f"Server {i}", "Active", "5")
        time.sleep(0.5)
        # Live automatically redraws the updated table
```
