---
name: cli-ux-patterns
description: Core guidelines for designing highly polished Command Line Interface (CLI) user experiences. Covers prompt rules, interactive options, dry-runs, undo commands, status updates, and scroll pollution prevention. Activate this skill when designing or refining terminal input/output flows.
---

# Command Line Interface (CLI) UX Patterns

A premium CLI tool should be intuitive, highly informative, responsive, and respectful of terminal scroll history. Follow these UI/UX design patterns.

---

## 1. Zero Pollution Confirmations

Confirmations or transient prompts must not leave leftover debris or redundant question/answer text in the console history after they are answered.

### The Transient Redraw Pattern
When showing interactive questions (e.g. Yes/No prompts for installations, deletions, or destructive modifications), clean up the screen when done:

```python
import sys
from rich.console import Console

console = Console()

def ask_yes_no_transient(question: str) -> bool:
    # Print the question
    console.print(f"[warning]?[/warning] {question} (y/N): ", end="")
    sys.stdout.flush()
    
    # Read user input
    try:
        response = sys.stdin.readline().strip().lower()
    except (KeyboardInterrupt, EOFError):
        response = "n"
        
    # Clear the confirmation line completely (up 1 line, clear line)
    console.print("\033[F\033[K", end="")
    
    return response == "y"
```

---

## 2. Dry-Run & Sandbox Modes

Any mutating action must be dry-runnable. Make dry-run modes explicit, non-destructive, and highly visual.

- **Dry-run Tag**: Print all simulated changes with a clear prefix like `[DRY-RUN]`. Use a distinct color (e.g. dark orange or purple).
- **Verification Logs**: Print the exact file write path, file line numbers, or commands that *would* be executed without applying them.
- **Example Pattern**:
```python
def write_file(filepath: str, content: str, dry_run: bool = False):
    if dry_run:
        console.print(f"[magenta][DRY-RUN][/magenta] Would write content to: [cyan]{filepath}[/cyan]")
        return
    
    # Actual file write logic
    with open(filepath, "w") as f:
        f.write(content)
```

---

## 3. Clear Hierarchy & Iconography

Use standard unicode icons coupled with color coding to guide the user's attention.

- `✓` Success (Emerald/Green): `[green]✓ Connected successfully![/green]`
- `✗` Error/Failure (Red): `[red]✗ Failed to connect to server[/red]`
- `⚠` Warning/Alert (Yellow): `[yellow]⚠ Local fallback environment detected[/yellow]`
- `ℹ` Information (Dim/Muted Cyan): `[dim cyan]ℹ Configuration path: .utim/config.json[/dim cyan]`

Ensure there is a space after icons and follow them with direct, action-oriented text.

---

## 4. Undo and Redo Mechanics

A robust CLI should allow rollback of operations. When performing operations:
1. Save the previous state or file content in `.utim_tmp/backups/`.
2. Compute the exact diff context.
3. In interactive sessions, list the turns and allow the user to roll back using `/undo` or `/rewind <index>`.
4. Inform the user of what was reverted:
   `✓ Reverted [cyan]main.py[/cyan] to turn #4 state.`

---

## 5. Non-Interactive Adaptability (TTY Detection)

CLI scripts must automatically adapt to non-interactive execution (e.g., CI/CD pipelines, piped streams):
```python
import sys

def check_interactivity():
    if not sys.stdin.isatty():
        # Running in piped or scripted mode (e.g., utim task "test" < input)
        # Disable interactive animations, prompts, and default to auto-accepting safe modifications.
        return False
    return True
```
