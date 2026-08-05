"""
Subagents management dialog for UTIM CLI.
/subagents — create, view, and delete custom subagents stored in .utim/subagents/

Each subagent is a directory:
  .utim/subagents/<id>/
      agent.json     — {"id": ..., "description": ..., "system_prompt": ...}
"""
import os
import json
import time
import shutil
import textwrap

from pathlib import Path
from utim_cli.config import config, get_utim_dir


# ─── Storage helpers ─────────────────────────────────────────────────────────

def _get_subagents_dir() -> Path:
    """Return the global .utim/subagents directory, creating it if needed."""
    d = get_utim_dir() / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_subagents() -> list:
    """Return list of subagent dicts: {id, description, system_prompt}.
    Uses prompt.md for system prompt text (resilient to JSON escaping errors),
    falling back to agent.json if prompt.md does not exist.
    """
    agents = []
    base = _get_subagents_dir()
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue

        agent_id = entry.name
        description = ""
        system_prompt = ""

        # 1. Read system_prompt from prompt.md or SYSTEM.md if present
        prompt_md = entry / "prompt.md"
        if not prompt_md.exists():
            prompt_md = entry / "SYSTEM.md"
        if not prompt_md.exists():
            prompt_md = entry / "agent.md"

        if prompt_md.exists():
            try:
                system_prompt = prompt_md.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        # 2. Read metadata from agent.json
        agent_json = entry / "agent.json"
        if agent_json.exists():
            try:
                data = json.loads(agent_json.read_text(encoding="utf-8"))
                agent_id = data.get("id", entry.name)
                description = data.get("description", description)
                if not system_prompt:
                    system_prompt = data.get("system_prompt", "")
            except Exception:
                # Fault tolerant fallback if agent.json has syntax errors
                if not description:
                    description = f"Subagent: {agent_id}"

        # If neither file exists or both failed, skip invalid folder
        if not prompt_md.exists() and not agent_json.exists():
            continue

        if not description:
            description = f"Subagent: {agent_id}"

        agents.append({
            "id": agent_id,
            "description": description,
            "system_prompt": system_prompt,
            "path": entry,
        })
    return agents


def _save_subagent(agent_id: str, description: str, system_prompt: str):
    """Write subagent prompt.md and agent.json to disk."""
    agent_dir = _get_subagents_dir() / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    # Save system prompt cleanly in prompt.md (plain Markdown, zero JSON escape issues)
    (agent_dir / "prompt.md").write_text(system_prompt, encoding="utf-8")
    # Save minimal metadata in agent.json
    data = {
        "id": agent_id,
        "description": description,
    }
    (agent_dir / "agent.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _delete_subagent(agent_id: str):
    """Remove subagent directory from disk."""
    agent_dir = _get_subagents_dir() / agent_id
    if agent_dir.exists():
        shutil.rmtree(agent_dir)


# ─── Interactive creation flow ────────────────────────────────────────────────

_SUBAGENT_SYSTEM_PROMPT_TEMPLATE = """\
You are a specialized AI subagent for UTIM CLI.

## Role
{description}

## Instructions
- Focus exclusively on tasks related to your role above.
- Be concise, precise, and technical.
- When writing code, follow the language and framework conventions already present in the project.
- Always explain key decisions briefly.
- If the task is outside your scope, say so and defer to the main UTIM agent.
"""


def _create_subagent_interactive(console):
    """Prompt the user for a subagent id + description and write a scaffold."""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.styles import Style as PTStyle

    pt_style = PTStyle.from_dict({"": "fg:#cdd6f4"})

    console.print("\n  [bold #cba6f7]Create New Subagent[/bold #cba6f7]")
    console.print(
        "  [dim]Subagents are stored in .utim/subagents/ and can be activated\n"
        "  by typing @<id> in the prompt before sending a message.[/dim]\n"
    )

    try:
        raw_id = pt_prompt("  Subagent ID (e.g. 'refactor-bot'): ", style=pt_style).strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw_id:
        console.print("  [red]✗ No ID provided. Cancelled.[/red]\n")
        return None

    # Sanitize
    agent_id = "".join(c for c in raw_id.lower() if c.isalnum() or c in ("-", "_"))
    if not agent_id:
        console.print("  [red]✗ Invalid ID. Use letters, digits, hyphens, or underscores.[/red]\n")
        return None

    existing_dir = _get_subagents_dir() / agent_id
    if (existing_dir / "agent.json").exists():
        console.print(f"  [yellow]⚠ Subagent '{agent_id}' already exists.[/yellow]\n")
        return agent_id

    try:
        desc = pt_prompt(
            "  One-line description (what does this subagent specialise in?): ",
            style=pt_style,
        ).strip()
    except (KeyboardInterrupt, EOFError):
        desc = ""

    if not desc:
        desc = f"Specialized subagent: {agent_id.replace('-', ' ').title()}"

    system_prompt = _SUBAGENT_SYSTEM_PROMPT_TEMPLATE.format(description=desc)

    try:
        _save_subagent(agent_id, desc, system_prompt)
        console.print(f"\n  [bold green]✓ Subagent '{agent_id}' created![/bold green]")
        console.print(f"  [dim]Activate by typing [bold white]@{agent_id}[/bold white] before your prompt.[/dim]\n")
        return agent_id
    except Exception as e:
        console.print(f"  [red]✗ Failed to create subagent: {e}[/red]\n")
        return None


# ─── Main dialog ──────────────────────────────────────────────────────────────

def _dialog_subagents(orchestrator=None):
    """Interactive /subagents dialog — view, create, and delete custom subagents."""
    from utim_cli.utim import console, _run_list_dialog  # type: ignore

    while True:
        agents = _load_subagents()

        # ── Build row list ────────────────────────────────────────────────────
        rows = []

        rows.append({
            "name": "⚡ Create New Subagent (with AI Prompt @subagents)",
            "desc": "Closes dialog and appends @subagents to prompt AI to design your subagent",
            "action": "create",
        })
        rows.append({
            "name": "📝 Create New Subagent (Interactive Form)",
            "desc": "Fill out ID & description manually in terminal",
            "action": "create_manual",
        })
        rows.append({
            "name": "❌ Exit",
            "desc": "Return to the chat screen",
            "action": "exit",
        })

        if agents:
            rows.append({
                "name": "─── Your Subagents ────────────────────────────────",
                "desc": "",
                "action": "header",
            })
            for ag in agents:
                rows.append({
                    "name": f"  🤖  @{ag['id']}",
                    "desc": ag["description"],
                    "action": "view",
                    "agent_id": ag["id"],
                    "agent": ag,
                })
                rows.append({
                    "name": f"       🗑  Delete '@{ag['id']}'",
                    "desc": "Permanently remove this subagent from disk",
                    "action": "delete",
                    "agent_id": ag["id"],
                })
        else:
            rows.append({
                "name": "  [dim]No subagents yet — use 'Create New Subagent' above.[/dim]",
                "desc": "",
                "action": "header",
            })

        # ── Render function ───────────────────────────────────────────────────
        def render_row(idx, row, selected):
            bg = "bg:#1e1e2e" if selected else ""
            act = row.get("action")

            if act == "exit":
                fg = "bold #f38ba8" if selected else "#f38ba8"
            elif act == "create":
                fg = "bold #89dceb" if selected else "#89dceb"
            elif act == "header":
                fg = "dim #585b70"
            elif act == "delete":
                fg = "bold #f38ba8 bg:#313244" if selected else "#f38ba8"
            elif act == "view":
                fg = "bold #89b4fa bg:#313244" if selected else "#89b4fa"
            else:
                fg = "fg:#cdd6f4" if selected else "fg:#a6adc8"

            term_w = shutil.get_terminal_size().columns
            desc = row.get("desc", "")
            desc_lines = textwrap.wrap(desc, width=max(20, term_w - 10)) if desc else []
            desc_block = ""
            for dl in desc_lines:
                desc_block += f"         {dl}\n"

            return [
                (bg, "  ➔ " if selected else "    "),
                (bg or fg, f"{row['name']}\n"),
                (bg or "class:dim", desc_block),
            ]

        action, idx = _run_list_dialog(
            rows,
            render_row,
            title="UTIM Subagents  [dim](Create or delete custom subagents)[/dim]",
            legend="UP/DOWN/J/K to navigate  •  ENTER to select  •  ESC/Q to exit",
        )

        if action != "select":
            break

        selected = rows[idx]
        act = selected.get("action")

        if act in ("exit", "header"):
            break

        elif act == "create":
            return "@subagents "

        elif act == "create_manual":
            from utim_cli.utim import _run_in_terminal_safe  # type: ignore
            _run_in_terminal_safe(lambda: _create_subagent_interactive(console))

        elif act == "view":
            ag = selected.get("agent", {})
            from utim_cli.utim import _run_captured_dialog  # type: ignore

            def _show_agent(console):
                console.print(f"\n  [bold #89b4fa]@{ag['id']}[/bold #89b4fa]")
                console.print(f"  [dim]{ag['description']}[/dim]\n")
                console.print("  [bold white]System Prompt:[/bold white]")
                for line in ag.get("system_prompt", "").splitlines():
                    console.print(f"  {line}")
                console.print()

            _run_captured_dialog(f"Subagent: @{ag['id']}", _show_agent)

        elif act == "delete":
            agent_id = selected["agent_id"]
            try:
                _delete_subagent(agent_id)
                console.print(f"\n  [bold green]✓ Subagent '@{agent_id}' deleted.[/bold green]\n")
            except Exception as e:
                console.print(f"\n  [bold red]✗ Failed to delete: {e}[/bold red]\n")
            time.sleep(0.8)

    return None
