import os
import json
import time
import shlex

from utim_cli.config import get_utim_dir

def _mcp_config_path():
    """Always resolves mcp.json to ~/.utim/mcp.json."""
    return str(get_utim_dir() / "mcp.json")

def _load_mcp_config():
    path = _mcp_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"mcpServers": {}}

def _save_mcp_config(cfg: dict):
    path = _mcp_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ─── Main MCP menu ────────────────────────────────────────────────────────────

def _dialog_mcp(orchestrator):
    """Interactive dialog to list, install, and manage MCP servers."""
    from utim_cli.mcp_client import mcp_manager
    from utim_cli.utim import console, _run_list_dialog, _prompt_input

    while True:
        mcp_config = _load_mcp_config()
        configured_servers = list(mcp_config.get("mcpServers", {}).keys())

        # Also include transient sessions not yet persisted
        for srv in mcp_manager.sessions.keys():
            if srv not in configured_servers:
                configured_servers.append(srv)

        rows = []
        rows.append({
            "name": "Install from Registry",
            "desc": "Choose from curated preset MCP servers (filesystem, GitHub, Postgres, etc.)",
            "action": "install",
        })
        rows.append({
            "name": "Add Custom MCP Server",
            "desc": "Configure any stdio or SSE/HTTP MCP server with custom command, args, and env",
            "action": "custom",
        })
        rows.append({
            "name": "Exit",
            "desc": "Return to the chat screen",
            "action": "cancel",
        })

        if configured_servers:
            rows.append({
                "name": "─── Configured Servers ─────────────────────────────",
                "desc": "",
                "action": "header",
            })
        for srv in configured_servers:
            is_connected = srv in mcp_manager.sessions
            srv_cfg = mcp_config.get("mcpServers", {}).get(srv, {})
            transport = srv_cfg.get("transport", "stdio").upper()
            if is_connected:
                tools_list = mcp_manager.server_tools.get(srv, [])
                tools_count = len(tools_list)
                preview = ", ".join(tools_list[:3]) + ("..." if tools_count > 3 else "")
                desc = f"Connected  [{transport}]  •  {tools_count} tools ({preview})"
            else:
                desc = f" Disconnected  [{transport}]"
            rows.append({
                "name": f"  {srv}",
                "desc": desc,
                "server_name": srv,
                "action": "manage",
            })

        def render_row(idx, row, selected):
            bg = "bg:#313244" if selected else ""
            act = row.get("action")
            if act == "install":
                fg = "bold #a6e3a1" if selected else "#a6e3a1"
            elif act == "custom":
                fg = "bold #89dceb" if selected else "#89dceb"
            elif act == "cancel":
                fg = "bold #f38ba8" if selected else "#f38ba8"
            elif act == "header":
                fg = "dim #585b70"
            elif act == "manage":
                is_conn = row["server_name"] in mcp_manager.sessions
                fg = ("bold white bg:#313244" if selected else "#cdd6f4") if is_conn else \
                     ("bold white bg:#313244" if selected else "#6c7086")
            else:
                fg = "fg:#cdd6f4"
            return [
                (bg, "  ➔ " if selected else "    "),
                (bg or fg, f"{row['name']}\n"),
                (bg or "class:dim", f"      {row['desc']}\n"),
            ]

        action, idx = _run_list_dialog(
            rows,
            render_row,
            title="Model Context Protocol (MCP) Manager",
            legend="UP/DOWN/J/K to navigate  •  ENTER to select  •  ESC/Q to quit",
        )

        if action != "select":
            return

        selected_row = rows[idx]
        act = selected_row.get("action")

        if act in ("cancel", "header"):
            return
        elif act == "install":
            _dialog_mcp_install(orchestrator)
        elif act == "custom":
            _dialog_mcp_add_custom(orchestrator)
        elif act == "manage":
            _dialog_mcp_manage(orchestrator, selected_row["server_name"])


# ─── Manage existing server ───────────────────────────────────────────────────

def _dialog_mcp_manage(orchestrator, server_name):
    """Sub-menu to manage an installed MCP server (view tools, edit, uninstall)."""
    from utim_cli.mcp_client import mcp_manager
    from utim_cli.utim import console, _run_list_dialog, _transient_status, _prompt_input

    while True:
        mcp_config = _load_mcp_config()
        srv_cfg = mcp_config.get("mcpServers", {}).get(server_name, {})
        is_connected = server_name in mcp_manager.sessions

        options = [
            {"name": "View Available Tools", "desc": f"List all tools exposed by {server_name}", "key": "view"},
            {"name": "View Configuration", "desc": "Show current command, args, and env for this server", "key": "config"},
            {"name": "Update Token / Env Vars", "desc": f"Update API keys or environment variables for {server_name}", "key": "update_env"},
            {"name": "Reconnect", "desc": f"Force reconnect to {server_name}", "key": "reconnect"},
            {"name": "Uninstall / Remove", "desc": f"Remove {server_name} from config and disconnect", "key": "uninstall"},
            {"name": "◀  Back", "desc": "Return to the MCP menu", "key": "back"},
        ]

        def render_option_row(idx, row, selected):
            bg = "bg:#313244" if selected else ""
            if row["key"] == "back":
                fg = "bold #f9e2af" if selected else "#f9e2af"
            elif row["key"] == "uninstall":
                fg = "bold #f38ba8" if selected else "#f38ba8"
            elif row["key"] == "reconnect":
                fg = "bold #89dceb" if selected else "#89dceb"
            elif row["key"] == "update_env":
                fg = "bold #f5c2e7" if selected else "#f5c2e7"
            else:
                fg = "bold #89b4fa" if selected else "#89b4fa"
            return [
                (bg, "  ➔ " if selected else "    "),
                (bg or fg, f"{row['name']}\n"),
                (bg or "class:dim", f"      {row['desc']}\n"),
            ]

        action, idx = _run_list_dialog(
            options,
            render_option_row,
            title=f"Manage MCP Server: {server_name}  [dim]({'connected' if is_connected else 'disconnected'})[/dim]",
            legend="UP/DOWN/J/K to navigate  •  ENTER to select  •  ESC/Q to go back",
        )

        if action != "select" or options[idx]["key"] == "back":
            return

        key = options[idx]["key"]

        if key == "view":
            console.print(f"\n[bold #89b4fa]Tools exposed by {server_name}:[/bold #89b4fa]\n")
            tools = mcp_manager.get_tools()
            prefix = f"{server_name}__"
            count = 0
            for t in tools:
                name = t["function"]["name"]
                if name.startswith(prefix):
                    count += 1
                    desc = t["function"]["description"]
                    console.print(f"  • [bold white]{name.replace(prefix, '')}[/bold white]")
                    console.print(f"    [dim]{desc[:120]}{'...' if len(desc) > 120 else ''}[/dim]\n")
            if count == 0:
                console.print("  [dim]No tools exposed or server not connected.[/dim]\n")
            _prompt_input("  Press Enter to return...")

        elif key == "config":
            console.print(f"\n[bold #89b4fa]Configuration for {server_name}:[/bold #89b4fa]\n")
            if srv_cfg:
                console.print(f"  [dim]command:[/dim]  [white]{srv_cfg.get('command', '')}[/white]")
                console.print(f"  [dim]args:[/dim]     [white]{' '.join(srv_cfg.get('args', []))}[/white]")
                transport = srv_cfg.get("transport", "stdio")
                console.print(f"  [dim]transport:[/dim][white]{transport}[/white]")
                if srv_cfg.get("url"):
                    console.print(f"  [dim]url:[/dim]      [white]{srv_cfg['url']}[/white]")
                if srv_cfg.get("cwd"):
                    console.print(f"  [dim]cwd:[/dim]      [white]{srv_cfg['cwd']}[/white]")
                env = srv_cfg.get("env", {})
                if env:
                    console.print(f"  [dim]env:[/dim]")
                    for k, v in env.items():
                        masked = v[:4] + "****" if len(v) > 8 else "****"
                        console.print(f"    [dim]{k}=[/dim][white]{masked}[/white]")
            else:
                console.print("  [dim]No configuration found.[/dim]")
            console.print()
            _prompt_input("  Press Enter to return...")

        elif key == "update_env":
            cfg = _load_mcp_config()
            srv = cfg.get("mcpServers", {}).get(server_name, {})
            existing_env = srv.get("env", {})

            console.print(f"\n[bold #f5c2e7]Update Environment Variables for [white]{server_name}[/white][/bold #f5c2e7]")
            if existing_env:
                console.print("  [dim]Current env keys (values masked):[/dim]")
                for k, v in existing_env.items():
                    masked = v[:4] + "****" if len(v) > 8 else "****"
                    console.print(f"    [dim]{k}=[/dim][white]{masked}[/white]")
            console.print("  [dim]Enter new values below. Leave blank to keep current value.\n[/dim]")

            try:
                new_env = dict(existing_env)  # copy
                for k in list(existing_env.keys()):
                    new_val = _prompt_input(f"  {k}: ").strip()
                    if new_val:
                        new_env[k] = new_val

                # Also allow adding new key/value pairs
                while True:
                    extra = _prompt_input("  Add extra env var KEY=VALUE (leave blank to finish): ").strip()
                    if not extra:
                        break
                    if "=" in extra:
                        ek, ev = extra.split("=", 1)
                        new_env[ek.strip()] = ev.strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Cancelled.[/dim]\n")
                continue

            srv["env"] = new_env
            cfg.setdefault("mcpServers", {})[server_name] = srv
            try:
                _save_mcp_config(cfg)
                console.print(f"  [bold #a6e3a1]✓ Saved updated env vars. Reconnecting...[/bold #a6e3a1]\n")
                _restart_with_spinner(server_name)
            except Exception as e:
                console.print(f"\n  [bold red]✗ Failed to save config: {e}[/bold red]\n")

        elif key == "reconnect":
            _transient_status([f"[dim]Reconnecting to {server_name}...[/dim]"], hold=0.3)
            try:
                mcp_manager.restart()
                if server_name in mcp_manager.sessions:
                    _transient_status([f"[bold #a6e3a1]✓ Reconnected to {server_name}.[/bold #a6e3a1]"], hold=1.5)
                else:
                    _transient_status([f"[bold red]✗ Could not reconnect to {server_name}.[/bold red]"], hold=2.0)
            except Exception as e:
                _transient_status([f"[red]Error: {e}[/red]"], hold=2.0)

        elif key == "uninstall":
            try:
                confirm = _prompt_input(f"\n  Remove '{server_name}'? This cannot be undone. [y/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                continue
            if confirm in ("y", "yes"):
                cfg = _load_mcp_config()
                cfg.setdefault("mcpServers", {}).pop(server_name, None)
                try:
                    _save_mcp_config(cfg)
                    mcp_manager.restart()
                    _transient_status([
                        f"[bold #a6e3a1]✓ Removed {server_name} from configuration.[/bold #a6e3a1]",
                    ], hold=1.5)
                    return
                except Exception as e:
                    _transient_status([f"[red]Error: {e}[/red]"], hold=2.0)


# ─── Add custom MCP server ────────────────────────────────────────────────────

def _dialog_mcp_add_custom(orchestrator):
    """
    Full-featured wizard to add any custom MCP server.
    Supports both stdio (command + args) and SSE/HTTP (URL-based) transports.
    """
    from utim_cli.utim import console, _run_list_dialog, _transient_status, _prompt_input

    console.print(
        "\n[bold #89dceb]╭─ Add Custom MCP Server ────────────────────────────────────────╮[/bold #89dceb]"
        "\n[bold #89dceb]│[/bold #89dceb]  Configure any MCP-compatible server manually.                 [bold #89dceb]│[/bold #89dceb]"
        "\n[bold #89dceb]│[/bold #89dceb]  Config is saved to: [dim]~/.utim/mcp.json[/dim]                      [bold #89dceb]│[/bold #89dceb]"
        "\n[bold #89dceb]╰────────────────────────────────────────────────────────────────╯[/bold #89dceb]\n"
    )

    # ── Step 1: Transport type ────────────────────────────────────────────────
    transport_rows = [
        {
            "name": "stdio  (recommended)",
            "desc": "Spawn a local process. Communicate via stdin/stdout. Works with npx, python, node, etc.",
            "key": "stdio",
        },
        {
            "name": "SSE / HTTP",
            "desc": "Connect to a remote or locally running HTTP server via Server-Sent Events.",
            "key": "sse",
        },
        {
            "name": "◀  Cancel",
            "desc": "Return to the MCP menu",
            "key": "cancel",
        },
    ]

    def render_transport(idx, row, selected):
        bg = "bg:#313244" if selected else ""
        if row["key"] == "cancel":
            fg = "bold #f38ba8" if selected else "#f38ba8"
        elif row["key"] == "stdio":
            fg = "bold #a6e3a1" if selected else "#a6e3a1"
        else:
            fg = "bold #89dceb" if selected else "#89dceb"
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['name']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    action, idx = _run_list_dialog(
        transport_rows,
        render_transport,
        title="Step 1 of 3 — Select Transport Type",
        legend="UP/DOWN to navigate  •  ENTER to select  •  ESC to cancel",
    )

    if action != "select" or transport_rows[idx]["key"] == "cancel":
        return

    transport = transport_rows[idx]["key"]

    # ── Step 2: Collect server details ───────────────────────────────────────
    try:
        console.print("\n[bold #89dceb]Step 2 — Server Details[/bold #89dceb]\n")

        server_name = _prompt_input("  Server name (kebab-case, e.g. my-server): ").strip().lower()
        server_name = "".join(c for c in server_name if c.isalnum() or c in ("-", "_"))
        if not server_name:
            console.print("  [red]✗ Server name is required.[/red]\n")
            return

        # Check for existing server with same name
        existing = _load_mcp_config()
        if server_name in existing.get("mcpServers", {}):
            try:
                overwrite = _prompt_input(
                    f"   Server '{server_name}' already exists. Overwrite? [y/N]: "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if overwrite not in ("y", "yes"):
                console.print("  [dim]Cancelled.[/dim]\n")
                return

        server_entry: dict = {"transport": transport}

        if transport == "stdio":
            command = _prompt_input("  Command (e.g. npx, python, node, uvx): ").strip()
            if not command:
                console.print("  [red]✗ Command is required.[/red]\n")
                return

            args_raw = _prompt_input(
                "  Arguments (space-separated, e.g. -y @modelcontextprotocol/server-filesystem /path): "
            ).strip()
            args = shlex.split(args_raw) if args_raw else []

            cwd = _prompt_input("  Working directory (leave blank for current dir): ").strip()

            server_entry["command"] = command
            server_entry["args"] = args
            if cwd:
                server_entry["cwd"] = cwd

        else:  # sse / http
            url = _prompt_input("  Server URL (e.g. http://localhost:3000/sse): ").strip()
            if not url:
                console.print("  [red]✗ URL is required.[/red]\n")
                return
            server_entry["url"] = url

        # ── Step 3: Environment variables ─────────────────────────────────────
        console.print("\n[bold #89dceb]Step 3 — Environment Variables[/bold #89dceb]")
        console.print("  [dim]Format: KEY=VALUE, KEY2=VALUE2  (leave blank if none)[/dim]\n")

        env: dict = {}
        env_raw = _prompt_input("  Env vars: ").strip()
        if env_raw:
            for pair in env_raw.split(","):
                pair = pair.strip()
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    env[k.strip()] = v.strip()
        if env:
            server_entry["env"] = env

    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Cancelled.[/dim]\n")
        return

    # ── Save and connect ──────────────────────────────────────────────────────
    cfg = _load_mcp_config()
    cfg.setdefault("mcpServers", {})[server_name] = server_entry

    try:
        _save_mcp_config(cfg)
    except Exception as e:
        console.print(f"\n  [bold red]✗ Failed to save config: {e}[/bold red]\n")
        return

    # Show preview of what was saved
    console.print(f"\n  [bold #a6e3a1]✓ Saved '{server_name}' to ~/.utim/mcp.json[/bold #a6e3a1]")
    if transport == "stdio":
        full_cmd = server_entry["command"] + " " + " ".join(server_entry.get("args", []))
        console.print(f"  [dim]Command:[/dim] [white]{full_cmd}[/white]")
    else:
        console.print(f"  [dim]URL:[/dim] [white]{server_entry.get('url', '')}[/white]")
    console.print()

    # Reconnect with spinner
    _restart_with_spinner(server_name)


def _restart_with_spinner(server_name: str):
    """Restart mcp_manager with a bouncing progress bar, then show result."""
    from utim_cli.utim import _transient_status
    import sys as _sys
    import threading as _threading
    import time as _time

    _done = _threading.Event()
    _error = [None]

    def _do_restart():
        try:
            from utim_cli.mcp_client import mcp_manager
            mcp_manager.restart()
        except Exception as exc:
            _error[0] = exc
        finally:
            _done.set()

    def _run_spinner():
        frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        enc = getattr(_sys.__stdout__, "encoding", None) or "utf-8"
        try:
            from utim_cli.constants import _IS_LEGACY_WIN
            is_legacy = _IS_LEGACY_WIN or enc.lower() not in ("utf-8", "utf8", "cp65001")
        except Exception:
            is_legacy = False
        if is_legacy:
            frames = ["-", "\\", "|", "/"]
            fill_ch, empty_ch = "#", "-"
        else:
            try:
                "█".encode(enc)
                fill_ch, empty_ch = "█", "░"
            except UnicodeEncodeError:
                fill_ch, empty_ch = "#", "-"

        bar_width = 30
        block = 6
        i = 0
        while not _done.is_set():
            cycle = (bar_width - block) * 2
            pos = i % cycle
            if pos > (bar_width - block):
                pos = cycle - pos
            bar = empty_ch * pos + fill_ch * block + empty_ch * (bar_width - pos - block)
            msg = f"\r  {frames[i % len(frames)]}  Connecting to {server_name}  [{bar[:bar_width]}]"
            try:
                _sys.__stdout__.write(msg)
                _sys.__stdout__.flush()
            except Exception:
                pass
            i += 1
            _time.sleep(0.07)
        try:
            _sys.__stdout__.write("\r" + " " * 72 + "\r")
            _sys.__stdout__.flush()
        except Exception:
            pass

    rt = _threading.Thread(target=_do_restart, daemon=True)
    st = _threading.Thread(target=_run_spinner, daemon=True)
    rt.start()
    st.start()
    rt.join()
    _done.set()
    st.join()

    if _error[0]:
        _transient_status([
            f"[bold red]✗ Error connecting to {server_name}: {_error[0]}[/bold red]",
            "[dim]The server was saved. Fix the command and try reconnecting via /mcp.[/dim]",
        ], hold=3.0)
        return

    from utim_cli.mcp_client import mcp_manager
    if server_name in mcp_manager.sessions:
        new_tools = [t for t in mcp_manager.get_tools() if t["function"]["name"].startswith(f"{server_name}__")]
        _transient_status([
            f"[bold #a6e3a1]✓ Connected to {server_name} successfully![/bold #a6e3a1]",
            f"[dim]Loaded {len(new_tools)} tools from {server_name}.[/dim]",
        ], hold=2.0)
    else:
        _transient_status([
            f"[bold red]✗ Could not connect to {server_name}.[/bold red]",
            "[dim]The server config was saved. Check command/URL and reconnect via /mcp.[/dim]",
        ], hold=3.0)


# ─── Registry install wizard ──────────────────────────────────────────────────

def _dialog_mcp_install(orchestrator):
    """Interactive wizard to install a preset MCP server from the registry."""
    from utim_cli.utim import console, _run_mcp_search_list_dialog, _transient_status, _prompt_input

    registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp_registry.json")
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            presets_config = json.load(f)
    except Exception:
        presets_config = {}

    presets = []
    for k, info in presets_config.items():
        desc = info["desc"]
        if info.get("author"):
            desc = f"{desc} (By {info['author']})"
        presets.append({"name": info["name"], "desc": desc, "key": k, "pkg": info.get("pkg", "")})

    presets.append({"name": "◀  Back to MCP Menu", "desc": "Return to the previous screen", "key": "back", "pkg": ""})

    def render_preset_row(idx, row, selected):
        bg = "bg:#313244" if selected else ""
        if row["key"] == "back":
            fg = "bold #f38ba8" if selected else "#f38ba8"
        else:
            fg = "bold #89b4fa" if selected else "#89b4fa"
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['name']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    action, idx = _run_mcp_search_list_dialog(
        presets,
        render_preset_row,
        title="Install MCP Server from Registry",
        legend="Type to filter  •  UP/DOWN to navigate  •  ENTER to select",
    )

    if action != "select" or presets[idx]["key"] == "back":
        return

    preset = presets[idx]
    key = preset["key"]
    preset_info = presets_config[key]

    console.print(
        f"\n[bold #42bcf5]╭─ Configure {preset['name']} ──────────────────────────╮[/bold #42bcf5]"
        f"\n[bold #42bcf5]│[/bold #42bcf5]  Saved to: [dim]~/.utim/mcp.json[/dim]               [bold #42bcf5]│[/bold #42bcf5]"
        f"\n[bold #42bcf5]╰──────────────────────────────────────────────────╯[/bold #42bcf5]\n"
    )

    server_name = key
    command = "npx"
    args = ["-y", preset_info["pkg"]]
    env = {}

    if "args" in preset_info:
        args.extend(preset_info["args"])

    try:
        for field in preset_info.get("fields", []):
            val = _prompt_input(field["prompt"]).strip()
            if not val and field.get("required", False):
                console.print(f"  [red]✗ {field['key']} is required.[/red]\n")
                return
            if not val:
                continue
            if field["type"] == "env":
                env[field["key"]] = val
            elif field["type"] == "arg":
                args.append(val)
            elif field["type"] == "arg_list":
                args.extend(p.strip() for p in val.split(","))
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Cancelled.[/dim]\n")
        return

    cfg = _load_mcp_config()
    cfg.setdefault("mcpServers", {})[server_name] = {
        "command": command,
        "args": args,
        "env": env,
    }

    try:
        _save_mcp_config(cfg)
    except Exception as e:
        console.print(f"\n  [bold red]✗ Failed to save config: {e}[/bold red]\n")
        return

    _restart_with_spinner(server_name)
