"""
Miniagents management dialog for UTIM CLI.
/miniagents — create, view, and delete lightweight script-based agents stored in .utim/miniagents/

Each miniagent is a small Python or JavaScript script:
  .utim/miniagents/<id>/
      agent.json   — {"id": ..., "description": ..., "lang": "python"|"js", "system_prompt": ...}
      agent.py     — (or agent.js) the script body
"""
import os
import json
import time
import shutil
import textwrap

from pathlib import Path
from utim_cli.config import config, get_utim_dir


# ─── Storage helpers ─────────────────────────────────────────────────────────

def _get_miniagents_dir() -> Path:
    """Return the global .utim/miniagents directory, creating it if needed."""
    d = get_utim_dir() / "miniagents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_miniagent_folder_size_kb(miniagent_path) -> float:
    """Calculate total size of all files inside a miniagent directory in Kilobytes (KB)."""
    p = Path(miniagent_path)
    if not p.exists():
        return 0.0
    total_bytes = 0
    if p.is_file():
        total_bytes = p.stat().st_size
    else:
        for f in p.rglob("*"):
            if f.is_file():
                total_bytes += f.stat().st_size
    return total_bytes / 1024.0


def get_miniagent_model_by_size(miniagent_path) -> str:
    """Determine primary model based on miniagent folder size:
    - < 100 KB: inclusionai/ling-3.0-flash:free
    - 100 KB to < 150 KB: nvidia/nemotron-3-ultra-550b-a55b:free
    - 150 KB to < 300 KB: deepseek/deepseek-v4-flash-0731
    - >= 300 KB: openai/gpt-5.6-luna-pro
    """
    size_kb = get_miniagent_folder_size_kb(miniagent_path)
    if size_kb < 100.0:
        return "inclusionai/ling-3.0-flash:free"
    elif size_kb < 150.0:
        return "nvidia/nemotron-3-ultra-550b-a55b:free"
    elif size_kb < 300.0:
        return "deepseek/deepseek-v4-flash-0731"
    else:
        return "openai/gpt-5.6-luna-pro"


def _load_miniagents() -> list:
    """Return list of miniagent dicts: {id, description, lang, system_prompt, folder_size_kb, primary_model}.
    Uses prompt.md for instructions (resilient to JSON escaping errors),
    falling back to agent.json if prompt.md does not exist.
    """
    agents = []
    base = _get_miniagents_dir()
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue

        agent_id = entry.name
        description = ""
        lang = "python"
        system_prompt = ""

        # 1. Read prompt.md if present
        prompt_md = entry / "prompt.md"
        if not prompt_md.exists():
            prompt_md = entry / "SYSTEM.md"
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
                lang = data.get("lang", "python")
                if not system_prompt:
                    system_prompt = data.get("system_prompt", "")
            except Exception:
                if not description:
                    description = f"Miniagent: {agent_id}"

        if not prompt_md.exists() and not agent_json.exists():
            continue

        if not description:
            description = f"Miniagent: {agent_id}"

        size_kb = get_miniagent_folder_size_kb(entry)
        primary_model = get_miniagent_model_by_size(entry)

        agents.append({
            "id": agent_id,
            "description": description,
            "lang": lang,
            "system_prompt": system_prompt,
            "path": entry,
            "folder_size_kb": size_kb,
            "primary_model": primary_model,
        })
    return agents


def _save_miniagent(agent_id: str, description: str, lang: str, system_prompt: str):
    """Write miniagent files (agent.json, prompt.md, and script stub) to disk."""
    agent_dir = _get_miniagents_dir() / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    # Save system prompt cleanly in prompt.md (plain Markdown, zero JSON escape issues)
    (agent_dir / "prompt.md").write_text(system_prompt, encoding="utf-8")
    # Save minimal metadata in agent.json
    data = {
        "id": agent_id,
        "description": description,
        "lang": lang,
    }
    (agent_dir / "agent.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # Write a stub script if it doesn't already exist
    ext = "py" if lang == "python" else "js"
    script_file = agent_dir / f"agent.{ext}"
    if not script_file.exists():
        if lang == "python":
            stub = f'# Miniagent: {agent_id}\n# {description}\n\ndef run(prompt: str) -> str:\n    """Execute the miniagent task."""\n    return f"Miniagent {agent_id!r} running: {{prompt}}"\n'
        else:
            stub = f'// Miniagent: {agent_id}\n// {description}\n\nfunction run(prompt) {{\n  return `Miniagent {agent_id} running: ${{prompt}}`;\n}}\n'
        script_file.write_text(stub, encoding="utf-8")


def _delete_miniagent(agent_id: str):
    """Remove miniagent directory from disk."""
    agent_dir = _get_miniagents_dir() / agent_id
    if agent_dir.exists():
        shutil.rmtree(agent_dir)


# ─── Interactive creation flow ────────────────────────────────────────────────

_MINIAGENT_SYSTEM_PROMPT_TEMPLATE = """\
You are a lightweight, fast-executing miniagent for UTIM CLI.

## Role
{description}

## Instructions
- Respond concisely and immediately — no long explanations.
- Focus only on your defined role above.
- Output should be directly usable (commands, code snippets, short answers).
- If asked something outside your scope, say so in one sentence.
"""


def _create_miniagent_interactive(console):
    """Prompt the user for a miniagent id, description, and language."""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.styles import Style as PTStyle

    pt_style = PTStyle.from_dict({"": "fg:#cdd6f4"})

    console.print("\n  [bold #f9e2af]Create New Miniagent[/bold #f9e2af]")
    console.print(
        "  [dim]Miniagents are lightweight script agents (Python or JS) stored in .utim/miniagents/\n"
        "  Activate by typing [bold white]@<id>[/bold white] before your prompt.[/dim]\n"
    )

    try:
        raw_id = pt_prompt("  Miniagent ID (e.g. 'quick-formatter'): ", style=pt_style).strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw_id:
        console.print("  [red]✗ No ID provided. Cancelled.[/red]\n")
        return None

    agent_id = "".join(c for c in raw_id.lower() if c.isalnum() or c in ("-", "_"))
    if not agent_id:
        console.print("  [red]✗ Invalid ID. Use letters, digits, hyphens, or underscores.[/red]\n")
        return None

    existing_dir = _get_miniagents_dir() / agent_id
    if (existing_dir / "agent.json").exists():
        console.print(f"  [yellow]Miniagent '{agent_id}' already exists.[/yellow]\n")
        return agent_id

    try:
        desc = pt_prompt(
            "  One-line description (what does this miniagent do?): ",
            style=pt_style,
        ).strip()
    except (KeyboardInterrupt, EOFError):
        desc = ""

    if not desc:
        desc = f"Lightweight miniagent: {agent_id.replace('-', ' ').title()}"

    try:
        lang_input = pt_prompt(
            "  Language — python or js [python]: ",
            style=pt_style,
        ).strip().lower()
    except (KeyboardInterrupt, EOFError):
        lang_input = ""

    lang = "js" if lang_input in ("js", "javascript", "node") else "python"
    system_prompt = _MINIAGENT_SYSTEM_PROMPT_TEMPLATE.format(description=desc)

    try:
        _save_miniagent(agent_id, desc, lang, system_prompt)
        ext = "py" if lang == "python" else "js"
        console.print(f"\n  [bold green]✓ Miniagent '{agent_id}' created! ({lang})[/bold green]")
        console.print(f"  [dim]Script: .utim/miniagents/{agent_id}/agent.{ext}[/dim]")
        console.print(f"  [dim]Activate with [bold white]@{agent_id}[/bold white] before your prompt.[/dim]\n")
        return agent_id
    except Exception as e:
        console.print(f"  [red]✗ Failed to create miniagent: {e}[/red]\n")
        return None


# ─── Main dialog ──────────────────────────────────────────────────────────────

def _dialog_miniagents(orchestrator=None):
    """Interactive /miniagents dialog — view, create, and delete miniagents."""
    from utim_cli.utim import console, _run_list_dialog  # type: ignore

    while True:
        agents = _load_miniagents()

        rows = []
        rows.append({
            "name": "Create New Miniagent (with AI Prompt @miniagents)",
            "desc": "Closes dialog and appends @miniagents to prompt AI to design your miniagent",
            "action": "create",
        })
        rows.append({
            "name": "Create New Miniagent (Interactive Form)",
            "desc": "Fill out ID & script details manually in terminal",
            "action": "create_manual",
        })
        rows.append({
            "name": "Exit",
            "desc": "Return to the chat screen",
            "action": "exit",
        })

        if agents:
            rows.append({
                "name": "─── Your Miniagents ────────────────────────────────",
                "desc": "",
                "action": "header",
            })
            for ag in agents:
                lang_icon = "" if ag["lang"] == "python" else ""
                rows.append({
                    "name": f"  {lang_icon}  @{ag['id']}",
                    "desc": f"[{ag['lang']}]  {ag['description']}",
                    "action": "view",
                    "agent_id": ag["id"],
                    "agent": ag,
                })
                rows.append({
                    "name": f"        Delete '@{ag['id']}'",
                    "desc": "Permanently remove this miniagent from disk",
                    "action": "delete",
                    "agent_id": ag["id"],
                })
        else:
            rows.append({
                "name": "  [dim]No miniagents yet — use 'Create New Miniagent' above.[/dim]",
                "desc": "",
                "action": "header",
            })

        def render_row(idx, row, selected):
            bg = "bg:#313244" if selected else ""
            act = row.get("action")

            if act == "exit":
                fg = "bold #f38ba8" if selected else "#f38ba8"
            elif act == "create":
                fg = "bold #f9e2af" if selected else "#f9e2af"
            elif act == "header":
                fg = "dim #585b70"
            elif act == "delete":
                fg = "bold white bg:#313244" if selected else "#6c7086"
            elif act == "view":
                fg = "bold white bg:#313244" if selected else "#cdd6f4"
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
            title="UTIM Miniagents  [dim](Create or delete script-based miniagents)[/dim]",
            legend="UP/DOWN/J/K to navigate  •  ENTER to select  •  ESC/Q to exit",
        )

        if action != "select":
            break

        selected = rows[idx]
        act = selected.get("action")

        if act in ("exit", "header"):
            break

        elif act == "create":
            return "@miniagents "

        elif act == "create_manual":
            from utim_cli.utim import _run_in_terminal_safe  # type: ignore
            _run_in_terminal_safe(lambda: _create_miniagent_interactive(console))

        elif act == "view":
            ag = selected.get("agent", {})
            from utim_cli.utim import _run_captured_dialog  # type: ignore

            def _show_agent(console):
                lang_icon = "" if ag["lang"] == "python" else ""
                console.print(f"\n  {lang_icon} [bold #f9e2af]@{ag['id']}[/bold #f9e2af]  [dim]({ag['lang']})[/dim]")
                console.print(f"  [dim]{ag['description']}[/dim]\n")
                script_path = ag["path"] / f"agent.{'py' if ag['lang'] == 'python' else 'js'}"
                if script_path.exists():
                    console.print(f"  [bold white]Script path:[/bold white] [dim]{script_path}[/dim]")
                console.print()

            _run_captured_dialog(f"Miniagent: @{ag['id']}", _show_agent)

        elif act == "delete":
            agent_id = selected["agent_id"]
            try:
                _delete_miniagent(agent_id)
                console.print(f"\n  [bold green]✓ Miniagent '@{agent_id}' deleted.[/bold green]\n")
            except Exception as e:
                console.print(f"\n  [bold red]✗ Failed to delete: {e}[/bold red]\n")
            time.sleep(0.8)

    return None
