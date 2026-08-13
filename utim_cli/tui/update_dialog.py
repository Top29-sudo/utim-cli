import sys
import threading
import time
import subprocess

def _dialog_auto_update():
    from utim_cli.utim import console, _run_mcp_search_list_dialog, _transient_status
    """Settings dialog to toggle auto-update and trigger a manual update check."""
    from utim_cli.config import config
    import sys, subprocess

    def _get_status_label():
        enabled = config.get("auto_update_enabled", False)
        if enabled is False:
            return "[bold red]DISABLED[/bold red]"
        return "[bold green]ENABLED[/bold green]"

    while True:
        enabled = config.get("auto_update_enabled", False)
        rows = [
            {"key": "toggle",  "label": f"Auto-Update: {_get_status_label()}",
             "desc": "Toggle automatic background updates on or off"},
            {"key": "check",   "label": "Check for Updates Now",
             "desc": "Immediately check npm registry and install if newer version found"},
            {"key": "back",    "label": "Back",
             "desc": "Return to previous menu"},
        ]

        def _render(idx, row, selected):
            bg = 'bg:#313244' if selected else ''
            if row["key"] == "back":
                fg = 'bold #f38ba8' if selected else '#f38ba8'
            elif row["key"] == "toggle":
                fg = 'bold #a6e3a1' if selected else '#a6e3a1'
            else:
                fg = 'bold #89b4fa' if selected else '#89b4fa'
            return [
                (bg, '  ➔ ' if selected else '    '),
                (bg or fg, f"{row['label']}\n"),
                (bg or 'class:dim', f"      {row['desc']}\n"),
            ]

        action, idx = _run_mcp_search_list_dialog(
            rows, _render,
            title="Auto-Update Settings",
            legend="ENTER to select, ESC to go back",
            search_prompt=" Search Settings: ",
            search_title="Filter Settings",
            list_title="Settings Options"
        )

        if action != "select" or rows[idx]["key"] == "back":
            return

        key = rows[idx]["key"]

        if key == "toggle":
            new_val = False if config.get("auto_update_enabled", False) else True
            config.set("auto_update_enabled", new_val)
            state_str = "enabled" if new_val else "disabled"
            _transient_status([
                f"[bold #a6e3a1]✓ Auto-update {state_str}.[/bold #a6e3a1]",
                "[dim]This setting is saved globally in ~/.utim/config.json[/dim]",
            ], hold=1.5)

        elif key == "check":
            import sys as _sys
            import threading as _threading
            import time as _time
            import requests as _req

            _done  = _threading.Event()
            _result = [None]   # (latest_ver, updated:bool)

            def _do_check():
                try:
                    resp = _req.get(
                        "https://registry.npmjs.org/@emend-ai/utim/latest",
                        timeout=8, headers={"Accept": "application/json"}
                    )
                    if resp.status_code != 200:
                        _result[0] = ("network_error", False)
                        return
                    latest = resp.json().get("version", "")
                    from utim_cli import __version__ as current

                    def pv(v):
                        return [int(x) for x in v.split(".") if x.isdigit()]

                    if pv(latest) <= pv(current):
                        _result[0] = (latest, False)  # already latest
                        return

                    # Install updates
                    subprocess.Popen(
                        [_sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "utim-cli"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    ).wait()
                    subprocess.Popen(
                        "npm install -g @emend-ai/utim@latest",
                        shell=(_sys.platform == "win32"),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    ).wait()
                    config.set("background_updated_version", latest)
                    _result[0] = (latest, True)
                except Exception as exc:
                    _result[0] = (str(exc), False)
                finally:
                    _done.set()

            def _run_check_spinner():
                frames = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
                enc = getattr(_sys.__stdout__, 'encoding', None) or 'utf-8'
                from utim_cli.constants import _IS_LEGACY_WIN
                is_legacy = _IS_LEGACY_WIN or enc.lower() not in ('utf-8', 'utf8', 'cp65001')
                if is_legacy:
                    frames = ["-", "\\", "|", "/"]
                    fill_ch, empty_ch = "#", "-"
                else:
                    try:
                        "█".encode(enc)
                        fill_ch, empty_ch = "█", "░"
                    except UnicodeEncodeError:
                        fill_ch, empty_ch = "#", "-"
                bar_w, block = 30, 6
                i = 0
                while not _done.is_set():
                    cycle = (bar_w - block) * 2
                    pos = i % cycle
                    if pos > (bar_w - block): pos = cycle - pos
                    bar = empty_ch * pos + fill_ch * block + empty_ch * max(0, bar_w - pos - block)
                    msg = f"\r  {frames[i % len(frames)]}  Checking for updates  [{bar[:bar_w]}]"
                    try: _sys.__stdout__.write(msg); _sys.__stdout__.flush()
                    except Exception: pass
                    i += 1
                    _time.sleep(0.07)
                try: _sys.__stdout__.write("\r" + " " * 72 + "\r"); _sys.__stdout__.flush()
                except Exception: pass

            ct = _threading.Thread(target=_do_check, daemon=True)
            st = _threading.Thread(target=_run_check_spinner, daemon=True)
            ct.start(); st.start()
            ct.join(); _done.set(); st.join()

            ver, updated = _result[0] if _result[0] else ("unknown", False)
            if ver == "network_error":
                _transient_status(["[bold red]Could not reach npm registry. Check your internet connection.[/bold red]"], hold=2.0)
            elif updated:
                _transient_status([
                    f"[bold #a6e3a1]✓ Updated to v{ver} successfully![/bold #a6e3a1]",
                    "[dim]Restart utim for the new version to take effect.[/dim]",
                ], hold=2.0)
                return
            else:
                _transient_status([
                    f"[bold #89b4fa]✓ Already on the latest version (v{ver}).[/bold #89b4fa]",
                ], hold=1.5)


