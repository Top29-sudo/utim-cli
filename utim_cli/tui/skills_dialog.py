"""
Skills management dialog for UTIM CLI.
/skills — activate, deactivate, delete, and create skills in .utim_tmp/skills/
"""
import os
import time
import textwrap
import shutil

from pathlib import Path
from utim_cli.config import config, get_utim_dir

def _get_skills_dir() -> Path:
    d = get_utim_dir() / "skills"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _load_skills():
    """Return list of skill dicts: {name, path, description, enabled} from global .utim/skills directories."""
    disabled: list = config.get("disabled_skills") or []
    if not isinstance(disabled, list):
        disabled = []

    skills = []
    seen = set()
    
    skill_dirs = [
        get_utim_dir() / "skills",
        get_utim_dir() / "agentskills",
        Path.home() / ".utim" / "skills",
        Path.home() / ".utim" / "agentskills",
        Path(".utim/skills"),
        Path(".utim/agentskills"),
        Path(".agents/skills"),
    ]

    for base_dir in skill_dirs:
        if not base_dir.exists() or not base_dir.is_dir():
            continue

        for entry in sorted(base_dir.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name in seen:
                continue

            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                skill_md = entry / "skill.md"
            if not skill_md.exists():
                continue

            seen.add(entry.name)
            description = ""
            try:
                content = skill_md.read_text(encoding="utf-8")
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        import yaml  # type: ignore
                        ydata = yaml.safe_load(parts[1]) or {}
                        description = ydata.get("description", "")
            except Exception:
                pass

            if not description:
                description = f"User skill: {entry.name}"

            skills.append({
                "name": entry.name,
                "path": skill_md,
                "description": description,
                "enabled": entry.name not in disabled,
            })

    return skills, disabled


def _save_disabled(disabled: list):
    config.set("disabled_skills", disabled)


def _create_skill_interactive(console):
    """Prompt the user for a skill name + description and write an empty scaffold."""
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.styles import Style as PTStyle

    pt_style = PTStyle.from_dict({"": "fg:#cdd6f4"})

    console.print("\n  [bold #cba6f7]Create New Skill[/bold #cba6f7]")
    console.print("  [dim]Skill files will be saved to ~/.utim/skills/<name>/SKILL.md[/dim]\n")

    try:
        raw_name = pt_prompt("  Skill name (kebab-case, e.g. my-skill): ", style=pt_style).strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if not raw_name:
        console.print("  [red]✗ No name provided. Cancelled.[/red]\n")
        return None

    # Sanitize
    skill_name = "".join(c for c in raw_name.lower() if c.isalnum() or c in ("-", "_"))
    if not skill_name:
        console.print("  [red]✗ Invalid name. Use letters, digits, hyphens, or underscores.[/red]\n")
        return None

    skill_dir = _get_skills_dir() / skill_name
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        console.print(f"  [yellow]⚠ Skill '{skill_name}' already exists. Opening its folder.[/yellow]\n")
        return skill_name

    try:
        desc = pt_prompt("  One-line description (what does this skill teach?): ", style=pt_style).strip()
    except (KeyboardInterrupt, EOFError):
        desc = ""

    if not desc:
        desc = f"Automatically learned guidelines for {skill_name.replace('-', ' ').title()}."

    title_name = skill_name.replace("-", " ").title()
    content = f"""---
name: {skill_name}
description: {desc}
---

# {title_name}

{desc}

## Guidelines

- Add your guidelines here. Each rule should be detailed and actionable.

## Examples

```
# Add concrete examples here
```
"""
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md.write_text(content, encoding="utf-8")
        console.print(f"\n  [bold green]✓ Skill '{skill_name}' created at:[/bold green]")
        console.print(f"  [dim]{skill_md}[/dim]\n")
        console.print("  [dim]Edit the file to fill in your custom guidelines.[/dim]\n")
        return skill_name
    except Exception as e:
        console.print(f"  [red]✗ Failed to create skill: {e}[/red]\n")
        return None


# ─── main dialog ─────────────────────────────────────────────────────────────

def _dialog_skills(orchestrator=None):
    """Interactive /skills dialog — toggle, create, delete skills."""
    from utim_cli.utim import console, _run_list_dialog  # type: ignore

    while True:
        skills, disabled = _load_skills()

        # ── Build row list ────────────────────────────────────────────────────
        rows = []

        rows.append({
            "name": "✅ Enable All Skills",
            "desc": "Activate every skill in .utim_tmp/skills/",
            "action": "enable_all",
        })
        rows.append({
            "name": "⬜ Disable All Skills",
            "desc": "Deactivate every skill (skills remain on disk)",
            "action": "disable_all",
        })
        rows.append({
            "name": "⚡ Create New Skill (with AI Prompt @skills)",
            "desc": "Closes dialog and appends @skills to prompt AI to design your skill",
            "action": "create",
        })
        rows.append({
            "name": "📝 Create New Skill (Interactive Form)",
            "desc": "Scaffold a new SKILL.md manually in terminal",
            "action": "create_manual",
        })
        rows.append({
            "name": "❌ Exit",
            "desc": "Return to the chat screen",
            "action": "exit",
        })

        if skills:
            rows.append({
                "name": "─── Your Skills ───────────────────────────────────",
                "desc": "",
                "action": "header",
            })
            for sk in skills:
                checkbox = "☑" if sk["enabled"] else "☐"
                rows.append({
                    "name": f"  {checkbox}  {sk['name']}",
                    "desc": sk["description"],
                    "action": "toggle",
                    "skill_name": sk["name"],
                    "enabled": sk["enabled"],
                })
                rows.append({
                    "name": f"       🗑  Delete '{sk['name']}'",
                    "desc": "Permanently remove this skill from disk",
                    "action": "delete",
                    "skill_name": sk["name"],
                })
        else:
            rows.append({
                "name": "  [dim]No skills yet — use 'Create New Skill' or ask the AI to create one.[/dim]",
                "desc": "",
                "action": "header",
            })

        # ── Render function ───────────────────────────────────────────────────
        def render_row(idx, row, selected):
            bg = "bg:#1e1e2e" if selected else ""
            act = row.get("action")

            if act == "exit":
                fg = "bold #f38ba8" if selected else "#f38ba8"
            elif act in ("enable_all", "disable_all"):
                fg = "bold #a6e3a1" if selected else "#a6e3a1"
            elif act in ("create", "create_manual"):
                fg = "bold #89dceb" if selected else "#89dceb"
            elif act == "header":
                fg = "dim #585b70"
            elif act == "delete":
                fg = ("bold #f38ba8 bg:#313244" if selected else "#f38ba8")
            elif act == "toggle":
                enabled = row.get("enabled", True)
                if enabled:
                    fg = ("bold #a6e3a1 bg:#313244" if selected else "#a6e3a1")
                else:
                    fg = ("fg:#cdd6f4 bg:#313244" if selected else "fg:#a6adc8")
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
            title="UTIM Skills Manager  [dim](Toggle, create, or delete skills)[/dim]",
            legend="UP/DOWN/J/K to navigate  •  ENTER to select  •  ESC/Q to exit",
        )

        if action != "select":
            break

        selected = rows[idx]
        act = selected.get("action")

        if act == "exit" or act == "header":
            break

        elif act == "enable_all":
            config.set("disabled_skills", [])
            console.print("\n  [bold green]✓ All skills enabled.[/bold green]\n")
            time.sleep(0.8)

        elif act == "disable_all":
            all_names = [sk["name"] for sk in skills]
            config.set("disabled_skills", all_names)
            console.print("\n  [bold yellow]⬜ All skills disabled.[/bold yellow]\n")
            time.sleep(0.8)

        elif act == "create":
            return "@skills "

        elif act == "create_manual":
            from utim_cli.utim import _run_in_terminal_safe  # type: ignore
            _run_in_terminal_safe(lambda: _create_skill_interactive(console))

        elif act == "toggle":
            skill_name = selected["skill_name"]
            disabled = config.get("disabled_skills") or []
            if not isinstance(disabled, list):
                disabled = []
            if skill_name in disabled:
                disabled.remove(skill_name)
                console.print(f"\n  [bold green]✓ Skill '{skill_name}' enabled.[/bold green]\n")
            else:
                disabled.append(skill_name)
                console.print(f"\n  [bold yellow]⬜ Skill '{skill_name}' disabled.[/bold yellow]\n")
            config.set("disabled_skills", disabled)
            time.sleep(0.5)

        elif act == "delete":
            skill_name = selected["skill_name"]
            skill_dir = _UTIM_SKILLS_DIR / skill_name
            try:
                shutil.rmtree(skill_dir)
                # Also remove from disabled list if present
                disabled = config.get("disabled_skills") or []
                if skill_name in disabled:
                    disabled.remove(skill_name)
                    config.set("disabled_skills", disabled)
                console.print(f"\n  [bold green]✓ Skill '{skill_name}' deleted.[/bold green]\n")
            except Exception as e:
                console.print(f"\n  [bold red]✗ Failed to delete: {e}[/bold red]\n")
            time.sleep(0.8)

    console.print("\n  [bold green]✓ Skills configuration saved.[/bold green]\n")
