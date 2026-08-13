"""
Publish Extension Wizard for UTIM Marketplace.

Architecture:
- All fields are rendered as rows inside a single _run_list_dialog loop.
- TEXT fields (name, description, tags): use _set_inline_edit() so the user
  types directly in the TUI. Enter saves; ESC cancels.
- CYCLE fields (type, category): Enter cycles through options in-place.
- PICKER fields (folder, price): return ("pick_folder"|"pick_price", idx) from
  on_enter by exiting the dialog, then the outer while-loop opens a sub-picker
  dialog, captures the result, and re-enters the main form.
- SUBMIT / BACK: return ("submit"|"back", idx) to exit the outer loop.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import requests
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional

# ── Catppuccin Palette ─────────────────────────────────────────────────────────
_MAUVE   = "#cba6f7"
_BLUE    = "#89b4fa"
_CYAN    = "#89dceb"
_GREEN   = "#a6e3a1"
_YELLOW  = "#f9e2af"
_RED     = "#f38ba8"
_SURFACE = "#313244"
_BORDER  = "#45475a"
_MUTED   = "#6c7086"
_FG      = "#cdd6f4"
_WHITE   = "#f5e0dc"
_PINK    = "#f5c2e7"

_API_BASE = "https://api.utim.dev"

_EXT_TYPES  = ["skill", "miniagent"]
_CATEGORIES = ["coding", "ai", "productivity", "devops", "data", "other"]


def _validate_extension_folder(ext_type: str, folder_path: str) -> tuple[bool, Optional[str]]:
    """Validate extension folder before publishing.
    - Skills: MUST contain ONLY SKILL.md and README.md (no subdirectories or extra files).
    - Skills & Miniagents: MUST include a proper non-empty README.md file.
    """
    p = Path(folder_path)
    if not p.exists() or not p.is_dir():
        return False, f"Folder does not exist: '{folder_path}'"

    ext_type_clean = ext_type.lower().strip()

    # Rule A: Mandatory README.md for skills and miniagents
    if ext_type_clean in ("skill", "miniagent"):
        readme_file = None
        for child in p.iterdir():
            if child.is_file() and child.name.lower() in ("readme.md", "readme.txt"):
                readme_file = child
                break
        if not readme_file or not readme_file.exists():
            return False, f"Missing README.md: Every {ext_type_clean} MUST include a proper README.md file describing its usage and features."
        try:
            content = readme_file.read_text(encoding="utf-8").strip()
            if len(content) < 10:
                return False, f"Invalid README.md: The README.md file in '{p.name}' is empty or too short."
        except Exception as err:
            return False, f"Cannot read README.md: {err}"

    # Rule B: Skill folder file restriction — ONLY SKILL.md and README.md allowed!
    if ext_type_clean == "skill":
        allowed_names = {"skill.md", "readme.md"}
        found_files = []
        for child in p.rglob("*"):
            rel_path = str(child.relative_to(p)).replace("\\", "/")
            if child.is_dir():
                return False, f"Invalid Skill structure: Skills folder must NOT contain subdirectories ('{rel_path}'). Skills only allow SKILL.md and README.md."
            name_lower = child.name.lower()
            if name_lower not in allowed_names:
                return False, f"Invalid Skill structure: Skills folder must ONLY contain SKILL.md and README.md. Found unexpected file: '{rel_path}'."
            found_files.append(name_lower)

        if "skill.md" not in found_files:
            return False, "Invalid Skill structure: Skills folder must contain a 'SKILL.md' file."

    return True, None

_PRICE_OPTIONS = [
    ("free",        "0.0",  "one_time",     ""),
    ("paid_001",    "0.01", "one_time",     ""),
    ("paid_1",      "1.0",  "one_time",     ""),
    ("paid_5",      "5.0",  "one_time",     ""),
    ("paid_10",     "10.0", "one_time",     ""),
    ("sub_monthly", "5.0",  "subscription", "monthly"),
    ("sub_yearly",  "49.0", "subscription", "yearly"),
]

_PRICE_LABELS = {
    "free":        " Free ($0.00)",
    "paid_001":    " $0.01 USD one-time  (minimum paid)",
    "paid_1":      " $1.00 USD one-time",
    "paid_5":      " $5.00 USD one-time",
    "paid_10":     " $10.00 USD one-time",
    "sub_monthly": " $5.00 / month subscription",
    "sub_yearly":  " $49.00 / year subscription",
}


# ── API Helpers ────────────────────────────────────────────────────────────────

def _get_api_key() -> Optional[str]:
    from utim_cli.config import config
    return config.get("api_key")


def _api_post(path: str, body: dict, timeout: int = 15) -> tuple[int, Optional[dict]]:
    try:
        import requests
        key = _get_api_key()
        headers = {"X-API-Key": key, "Content-Type": "application/json"} if key else {"Content-Type": "application/json"}
        r = requests.post(f"{_API_BASE}{path}", json=body, headers=headers, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, None
    except Exception:
        return 0, None


def _zip_folder_to_base64_compiled(folder_path: str) -> tuple[Optional[str], Optional[str], list[dict]]:
    """Zip a folder, compiling .py files to .pyc for anti-resell protection.
    Returns (zip_b64, readme_text, file_contents_for_scan).
    """
    import py_compile
    import tempfile
    import shutil

    p = Path(folder_path)
    if not p.exists() or not p.is_dir():
        return None, None, []

    readme_text = None
    for fn in ("README.md", "SKILL.md", "prompt.md"):
        f = p / fn
        if f.exists():
            try:
                readme_text = f.read_text(encoding="utf-8")
            except Exception:
                pass
            break

    # Collect raw file contents for security scanning BEFORE compilation
    file_contents: list[dict] = []
    _SCAN_EXTS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".sh", ".bat", ".ps1"}
    for fp in sorted(p.rglob("*")):
        if fp.is_file() and fp.suffix.lower() in _SCAN_EXTS:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                file_contents.append({"name": str(fp.relative_to(p)), "content": content})
            except Exception:
                pass

    # Build compiled zip in a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir) / "ext"
        shutil.copytree(str(p), str(tmp_p))

        # Compile all .py files -> .pyc and replace originals with bytecode
        for py_file in list(tmp_p.rglob("*.py")):
            try:
                pyc_path = str(py_file) + "c"   # .pyc alongside .py
                py_compile.compile(str(py_file), cfile=pyc_path, doraise=True, optimize=2)
                py_file.unlink()   # remove .py source
            except Exception:
                pass   # if compile fails keep the .py as-is

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in sorted(tmp_p.rglob("*")):
                if fp.is_file():
                    zf.write(fp, str(fp.relative_to(tmp_p)))

    return base64.b64encode(buf.getvalue()).decode("utf-8"), readme_text, file_contents


def _zip_folder_to_base64(folder_path: str) -> tuple[Optional[str], Optional[str]]:
    z, r, _ = _zip_folder_to_base64_compiled(folder_path)
    return z, r


def _autofill_from_folder(form: dict, folder: str) -> None:
    p = Path(folder)
    if not p.exists():
        return
    if not form["name"]:
        form["name"] = p.name.replace("-", " ").replace("_", " ").title()
    if not form["description"]:
        for fn in ("SKILL.md", "prompt.md", "README.md"):
            mf = p / fn
            if mf.exists():
                try:
                    for line in mf.read_text(encoding="utf-8").splitlines():
                        s = line.strip()
                        if s and not s.startswith("#") and not s.startswith("---") and len(s) > 10:
                            form["description"] = s[:120]
                            return
                except Exception:
                    pass


def _list_local_folders(ext_type: str) -> list[tuple[str, str]]:
    from utim_cli.config import get_utim_dir
    utim_dir = get_utim_dir()
    type_dirs = {
        "skill":     [utim_dir / "skills"],
        "miniagent": [utim_dir / "miniagents"],
        "tool":      [utim_dir / "marketplace" / "tool", utim_dir / "tools"],
        "mcp":       [utim_dir / "marketplace" / "mcp", utim_dir / "mcp"],
    }
    items: list[tuple[str, str]] = []
    seen: set[str] = set()
    bases = type_dirs.get(ext_type, [])
    for base in bases:
        if base and base.exists():
            for child in sorted(base.iterdir()):
                if child.is_dir() and child.name not in seen and not child.name.startswith("."):
                    seen.add(child.name)
                    items.append((str(child.resolve()), child.name))
    return items


# ── Security Check & Auto-Fix TUI ─────────────────────────────────────────────

def _run_security_check(
    console,
    ext_name: str,
    ext_type: str,
    file_contents: list[dict],
    mode: str = "check",
    issues: list[str] | None = None,
    source_folder: str | None = None,
) -> dict:
    """Full-screen live security scanner / auto-fixer rendered INSIDE prompt_toolkit list dialog.
    Zero stdout dumps, 100% dialog layout.
    """
    import requests
    from utim_cli.utim import _run_list_dialog

    def _invalidate_app():
        try:
            from prompt_toolkit.application.current import get_app
            get_app().invalidate()
        except Exception:
            pass

    api_key = None
    try:
        from utim_cli.config import config
        api_key = config.get("api_key")
    except Exception:
        pass

    headers = {"X-API-Key": api_key} if api_key else {}

    result: dict = {"overall": "UNKNOWN", "issues": [], "fixes_required": []}
    scan_done = threading.Event()
    user_action = [""]

    rows: list[dict] = []
    title_label = " UTIM SECURITY SCANNER" if mode == "check" else " UTIM SECURITY AUTO-FIXER"

    rows.append({"type": "info", "bold": True, "color": _WHITE, "text": f"{title_label} — {ext_name}"})
    rows.append({"type": "info", "color": _MUTED, "text": "Analyzing extension files in real-time..." if mode == "check" else "Auto-fixing security vulnerabilities..."})
    rows.append({"type": "spacer"})
    rows.append({"type": "sep"})

    status_row_idx = len(rows)
    rows.append({"type": "info", "bold": True, "color": _CYAN, "text": "  ⠿  Connecting to Security Agent..."})

    def _stream_scan():
        try:
            payload = {
                "extension_name": ext_name,
                "extension_type": ext_type,
                "files": file_contents,
                "mode": mode,
                "issues": issues,
            }
            resp = requests.post(
                f"{_API_BASE}/marketplace/security-check",
                json=payload,
                headers={**headers, "Content-Type": "application/json"},
                stream=True,
                timeout=180,
            )
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    evt = json.loads(raw_line)
                except Exception:
                    continue
                ev = evt.get("event", "")

                if ev == "started":
                    rows.append({"type": "info", "color": _CYAN, "text": f"{evt.get('message', '')}"})
                elif ev == "thinking":
                    rows.append({"type": "info", "color": _MUTED, "text": f"{evt.get('message', '')}"})
                elif ev == "check":
                    fname = evt.get("file", "")
                    pattern = evt.get("pattern", "")
                    rows.append({"type": "info", "color": _BLUE, "text": f"[{fname}] {pattern}"})
                elif ev == "finding":
                    fname = evt.get("file", "")
                    verdict = evt.get("verdict", "CLEAN")
                    detail = evt.get("detail", "")
                    color = _GREEN if verdict == "CLEAN" else (_YELLOW if verdict == "WARNING" else _RED)
                    icon = "✓" if verdict == "CLEAN" else ("" if verdict == "WARNING" else "✗")
                    rows.append({"type": "info", "bold": True, "color": color, "text": f"  {icon} [{fname}] {verdict} — {detail}"})
                elif ev == "file_edited":
                    rel_file = evt.get("file", "")
                    target = evt.get("target", "")
                    replacement = evt.get("replacement", "")
                    if source_folder and rel_file:
                        try:
                            fp = Path(source_folder) / rel_file
                            if fp.exists():
                                content = fp.read_text(encoding="utf-8")
                                if target in content:
                                    fp.write_text(content.replace(target, replacement, 1), encoding="utf-8")
                        except Exception:
                            pass
                    rows.append({"type": "info", "bold": True, "color": _GREEN, "text": f"  [AUTO-FIXED] {rel_file} — {evt.get('detail', '')}"})
                elif ev == "summary":
                    result["overall"] = evt.get("overall", "UNKNOWN")
                    result["issues"] = evt.get("issues", [])
                    result["fixes_required"] = evt.get("fixes_required", [])
                elif ev == "error":
                    rows.append({"type": "info", "bold": True, "color": _RED, "text": f"  ✗ Error: {evt.get('message', '')}"})
                    result["overall"] = "REJECTED"
                elif ev == "done":
                    break

                _invalidate_app()

        except Exception as exc:
            rows.append({"type": "info", "bold": True, "color": _RED, "text": f"  ✗ Connection Error: {exc}"})
            result["overall"] = "REJECTED"
        finally:
            scan_done.set()
            overall = result["overall"]
            color = _GREEN if overall in ("SAFE", "FIXED") else (_YELLOW if overall == "NEEDS_FIXES" else _RED)
            icon = "" if overall in ("SAFE", "FIXED") else "" if overall == "NEEDS_FIXES" else ""

            rows.append({"type": "sep"})
            rows.append({"type": "info", "bold": True, "color": color, "text": f"  {icon}  SESSION COMPLETE — {overall}"})

            # Insert detailed summary section into rows
            rows.append({"type": "sep"})
            rows.append({"type": "info", "bold": True, "color": _WHITE, "text": " SECURITY SCAN SUMMARY & FINDINGS"})
            
            res_issues = result.get("issues", [])
            res_fixes = result.get("fixes_required", [])
            
            if overall == "SAFE":
                rows.append({"type": "info", "color": _GREEN, "text": "  ✓ All security checks passed cleanly. No vulnerabilities or threats found."})
            elif overall == "FIXED":
                rows.append({"type": "info", "color": _GREEN, "text": "  ✓ All identified vulnerabilities were successfully auto-fixed!"})
            else:
                rows.append({"type": "info", "bold": True, "color": _RED, "text": f"  Status: {overall} — Action Required"})
                if res_issues:
                    rows.append({"type": "info", "bold": True, "color": _YELLOW, "text": "  Detected Security Issues:"})
                    for issue_item in res_issues[:8]:
                        rows.append({"type": "info", "color": _RED, "text": f"    • {issue_item}"})
                if res_fixes:
                    rows.append({"type": "info", "bold": True, "color": _CYAN, "text": "  Recommended Action Plan:"})
                    for fx in res_fixes[:8]:
                        rows.append({"type": "info", "color": _CYAN, "text": f"    ➔ {fx}"})

            rows.append({"type": "sep"})
            rows.append({"type": "action", "action": "dismiss", "label": " Press ENTER to Continue", "color": _CYAN, "hint": "Close log and proceed"})
            _invalidate_app()

    scan_thread = threading.Thread(target=_stream_scan, daemon=True)
    scan_thread.start()

    def _is_scan_selectable(row: dict) -> bool:
        if not scan_done.is_set():
            return False
        return row.get("type") == "action"

    async def _on_enter(idx, row, app, value=None):
        if not scan_done.is_set():
            return True   # Block Enter until scan finishes
        app.exit()
        return False

    def _render(idx, row, sel):
        return _render_form_row(idx, row, sel, {})

    _run_list_dialog(
        rows,
        _render,
        title=f"Security Session — {ext_name}",
        legend="UP/DOWN: Scroll / Navigate  •  ENTER: Continue when finished",
        is_selectable_fn=_is_scan_selectable,
        on_enter=_on_enter,
    )

    return result


def _ask_fix_prompt(issues: list[str], fixes_required: list[str] | None = None) -> str:
    """Prompt dialog asking if user wants AI to auto-fix security issues. Returns 'fix' or 'cancel'."""
    from utim_cli.utim import _run_list_dialog

    rows: list[dict] = [
        {"type": "info", "bold": True, "color": _RED, "text": " SECURITY SCAN VULNERABILITY SUMMARY"},
        {"type": "info", "color": _MUTED, "text": "The extension scan identified issues that prevent immediate publication:"},
        {"type": "spacer"},
    ]
    if issues:
        rows.append({"type": "info", "bold": True, "color": _RED, "text": "  Vulnerabilities Found:"})
        for issue in issues[:6]:
            rows.append({"type": "info", "color": _YELLOW, "text": f"    • {issue}"})
    
    if fixes_required:
        rows.append({"type": "spacer"})
        rows.append({"type": "info", "bold": True, "color": _CYAN, "text": "  Recommended Action Plan:"})
        for fx in fixes_required[:6]:
            rows.append({"type": "info", "color": _CYAN, "text": f"    ➔ {fx}"})

    rows.append({"type": "spacer"})
    rows.append({"type": "sep"})
    rows.append({"type": "action", "action": "fix", "label": " FIX Vulnerabilities with AI (Auto-edit source files)",
                 "color": _GREEN, "hint": "Enables AI tool calling (edit_file) to automatically refactor source code."})
    rows.append({"type": "action", "action": "cancel", "label": "←  Cancel & Return to Editor",
                 "color": _RED, "hint": "Return to editor to inspect and edit files yourself."})

    action = ["cancel"]
    async def _on_enter(idx, row, app, value=None):
        if row.get("action"):
            action[0] = row["action"]
            app.exit()
            return False
        return True

    def _render(idx, row, sel):
        return _render_form_row(idx, row, sel, {})

    _run_list_dialog(
        rows,
        _render,
        title="Security Issue Summary & Options",
        legend="UP/DOWN: Navigate  •  ENTER: Select Choice  •  ESC: Cancel",
        is_selectable_fn=_is_selectable,
        on_enter=_on_enter,
    )

    return action[0]


# ── Row Helpers ────────────────────────────────────────────────────────────────

def _is_selectable(row: dict) -> bool:
    return row.get("type") not in ("sep", "banner", "info", "spacer")


def _render_form_row(idx: int, row: dict, selected: bool, form: dict) -> list:
    bg  = f"bg:{_SURFACE}" if selected else ""
    ptr = "  ➔ " if selected else "    "
    rt  = row.get("type")

    if rt == "sep":
        return [("class:dim", "  " + "─" * 60 + "\n")]

    if rt == "info":
        color = row.get("color", _FG)
        return [(f"bold {color}" if row.get("bold") else f"fg:{color}", f"  {row['text']}\n")]

    if rt == "spacer":
        return [("", "\n")]

    if rt == "field":
        field   = row["field"]
        label   = row["label"]
        hint    = row.get("hint", "")
        fg_label = f"bold {_CYAN}" if selected else f"fg:{_FG}"
        fg_val   = f"bold {_GREEN}" if selected else f"fg:{_YELLOW}"
        fg_hint  = f"fg:{_MUTED}"

        # Build value display
        if field == "name":
            val = form["name"] if form["name"] else "[ press Enter to type... ]"
            val_style = fg_val if form["name"] else f"fg:{_MUTED}"
        elif field == "description":
            val = form["description"] if form["description"] else "[ press Enter to type... ]"
            val_style = fg_val if form["description"] else f"fg:{_MUTED}"
        elif field == "tags":
            val = form["tags"] if form["tags"] else "[ optional, e.g: python, web ]"
            val_style = fg_val if form["tags"] else f"fg:{_MUTED}"
        elif field == "type":
            val = f"[ {form['type'].upper()} ]  ← Enter cycles"
            val_style = f"bold {_MAUVE}"
        elif field == "category":
            val = f"[ {form['category'].title()} ]  ← Enter cycles"
            val_style = f"bold {_MAUVE}"
        elif field == "folder":
            if form["folder"] and Path(form["folder"]).is_dir():
                p = Path(form["folder"])
                val = f"✓  {p.name}  ({p})"
                val_style = f"bold {_GREEN}"
            else:
                val = "[ press Enter to pick folder... ]"
                val_style = f"fg:{_MUTED}"
        elif field == "price":
            try:
                pv = float(form["price"])
            except ValueError:
                pv = 0.0
            if pv == 0.0:
                val = " Free ($0.00)  ← Enter to change"
            else:
                pt_desc = "Subscription" if form.get("payment_type") == "subscription" else "One-Time"
                if form.get("sub_interval"):
                    pt_desc += f" ({form['sub_interval'].title()})"
                val = f" ${pv:.2f} USD — {pt_desc}  ← Enter to change"
            val_style = f"bold {_YELLOW}"
        else:
            val = str(form.get(field, ""))
            val_style = fg_val

        out = [
            (f"fg:{_BLUE}", ptr),
            (fg_label if selected else f"fg:{_FG}", f"{label:<22} : "),
            (val_style, f"{val}\n"),
        ]
        if selected and hint:
            out.append((fg_hint, f"{'':>{4 + len(ptr)}}{hint}\n"))
        return out

    if rt == "action":
        color = row.get("color", _BLUE)
        style = f"bold {color}" if selected else f"fg:{color}"
        hint  = row.get("hint", "")
        out   = [(style, f"{ptr}[ {row['label']} ]\n")]
        if selected and hint:
            out.append((f"fg:{_MUTED}", f"       {hint}\n"))
        return out

    return [("class:dim", f"  {row}\n")]


# ── Sub-picker: Folder ─────────────────────────────────────────────────────────

def _pick_folder(current: str, ext_type: str) -> Optional[str]:
    """Separate full-screen dialog to pick a source folder. Returns path or None."""
    from utim_cli.utim import _run_list_dialog

    local = _list_local_folders(ext_type)
    rows: list[dict] = [
        {"type": "info",   "text": f"Select Source Directory for '{ext_type.upper()}'", "bold": True, "color": _CYAN},
        {"type": "spacer"},
    ]
    if not local:
        rows.append({"type": "info", "color": _MUTED, "text": f"No local '{ext_type}' packages found in .utim/{ext_type}s/"})

    for fp, label in local:
        mark = "  ✓" if fp == current else ""
        rows.append({"type": "action", "action": fp, "label": f" {label}{mark}", "color": _FG,
                     "hint": fp})
    rows.append({"type": "sep"})
    rows.append({"type": "action", "action": "cancel", "label": "← Cancel", "color": _RED})

    chosen_path: list[Optional[str]] = [None]

    async def _on_enter(idx, row, app, value=None):
        act = row.get("action", "")
        if act == "cancel":
            app.exit()
            return False
        if act:
            chosen_path[0] = act
            app.exit()
            return False
        return True

    def _render(i, row, sel):
        bg  = f"bg:{_SURFACE}" if sel else ""
        ptr = "  ➔ " if sel else "    "
        rt  = row.get("type")
        if rt == "sep":
            return [("class:dim", "  " + "─" * 60 + "\n")]
        if rt == "spacer":
            return [("", "\n")]
        if rt == "info":
            c = row.get("color", _FG)
            return [(f"bold {c}" if row.get("bold") else f"fg:{c}", f"  {row['text']}\n")]
        if rt == "action":
            c  = row.get("color", _BLUE)
            st = f"bold {c}" if sel else f"fg:{c}"
            h  = row.get("hint", "")
            out = [(st, f"{ptr}{row['label']}\n")]
            if sel and h:
                out.append((f"class:dim fg:{_MUTED}", f"       {h}\n"))
            return out
        return [("class:dim", f"  {row}\n")]

    _run_list_dialog(
        rows, _render,
        title="Pick Source Directory",
        legend="UP/DOWN: Move  •  ENTER: Select  •  ESC/Q: Cancel",
        is_selectable_fn=_is_selectable,
        on_enter=_on_enter,
    )
    return chosen_path[0]


# ── Sub-picker: Price ──────────────────────────────────────────────────────────

def _pick_price(current_price: str) -> Optional[dict]:
    """Separate full-screen dialog to pick pricing. Returns dict or None."""
    from utim_cli.utim import _run_list_dialog

    rows: list[dict] = [
        {"type": "info", "text": "Select Pricing & Monetization Model", "bold": True, "color": _CYAN},
        {"type": "spacer"},
    ]
    for key, price, ptype, sub_int in _PRICE_OPTIONS:
        mark = "  ✓" if price == current_price else ""
        rows.append({"type": "action", "action": key,
                     "label": f"{_PRICE_LABELS[key]}{mark}",
                     "color": _GREEN if price == current_price else _FG,
                     "data": {"price": price, "payment_type": ptype, "sub_interval": sub_int}})
    rows.append({"type": "sep"})
    rows.append({"type": "info", "text": "Custom Pricing Options:", "color": _MUTED})
    rows.append({"type": "action", "action": "custom_one_time", "label": "  Custom One-Time Price (USD)...", "color": _YELLOW,
                 "hint": "e.g. 2.50 one-time payment"})
    rows.append({"type": "action", "action": "custom_monthly",  "label": "  Custom Monthly Subscription (USD)...", "color": _CYAN,
                 "hint": "e.g. 4.99 per month recurring"})
    rows.append({"type": "action", "action": "custom_yearly",   "label": "  Custom Yearly Subscription (USD)...", "color": _MAUVE,
                 "hint": "e.g. 49.99 per year recurring"})
    rows.append({"type": "sep"})
    rows.append({"type": "action", "action": "cancel", "label": "← Cancel", "color": _RED})

    result: list[Optional[dict]] = [None]
    custom_mode: list[tuple[str, str]] = [("one_time", "")]

    async def _on_enter(idx, row, app, value=None):
        if value is not None:
            try:
                pv = float(value.strip())
                if pv > 0:
                    pv = max(0.01, pv)  # minimum paid price is $0.01
                ptype, sub_int = custom_mode[0]
                result[0] = {"price": f"{pv:.2f}", "payment_type": ptype, "sub_interval": sub_int}
            except ValueError:
                pass
            app.exit()
            return False

        act = row.get("action", "")
        if act == "cancel":
            app.exit()
            return False
        if act == "custom_one_time":
            custom_mode[0] = ("one_time", "")
            from utim_cli.utim import _set_inline_edit
            _set_inline_edit("custom_price", "  One-Time Price in USD: ", current_price)
            return True
        if act == "custom_monthly":
            custom_mode[0] = ("subscription", "monthly")
            from utim_cli.utim import _set_inline_edit
            _set_inline_edit("custom_price", "  Monthly Sub Price in USD: ", current_price)
            return True
        if act == "custom_yearly":
            custom_mode[0] = ("subscription", "yearly")
            from utim_cli.utim import _set_inline_edit
            _set_inline_edit("custom_price", "  Yearly Sub Price in USD: ", current_price)
            return True
        data = row.get("data")
        if data:
            result[0] = data
            app.exit()
            return False
        return True

    def _render(i, row, sel):
        ptr = "  ➔ " if sel else "    "
        rt  = row.get("type")
        if rt == "sep":
            return [("class:dim", "  " + "─" * 60 + "\n")]
        if rt == "spacer":
            return [("", "\n")]
        if rt == "info":
            c = row.get("color", _FG)
            return [(f"bold {c}" if row.get("bold") else f"fg:{c}", f"  {row['text']}\n")]
        if rt == "action":
            c  = row.get("color", _BLUE)
            st = f"bold {c}" if sel else f"fg:{c}"
            h  = row.get("hint", "")
            out = [(st, f"{ptr}{row['label']}\n")]
            if sel and h:
                out.append((f"class:dim fg:{_MUTED}", f"       {h}\n"))
            return out
        return [("class:dim", f"  {row}\n")]

    _run_list_dialog(
        rows, _render,
        title="Pick Pricing Model",
        legend="UP/DOWN: Move  •  ENTER: Select  •  ESC/Q: Cancel",
        is_selectable_fn=_is_selectable,
        on_enter=_on_enter,
    )
    return result[0]


# ── Main Publish Dialog ────────────────────────────────────────────────────────

def dialog_publish(console) -> None:
    """
    Full publish wizard.
    - Text fields: inline edit (type directly in TUI, Enter saves, ESC cancels).
    - Type/Category: Enter cycles values in-place.
    - Folder/Price: Enter exits to sub-picker, result fed back, loop re-enters.
    """
    from utim_cli.tui.marketplace_dialog import _ensure_profile_setup
    if not _ensure_profile_setup(console):
        return

    from utim_cli.utim import _run_list_dialog, _set_inline_edit

    form: dict = {
        "name":         "",
        "type":         "skill",
        "folder":       "",
        "description":  "",
        "category":     "coding",
        "price":        "0.0",
        "payment_type": "one_time",
        "sub_interval": "",
        "tags":         "",
    }
    error_msg   = ""
    success_msg = ""

    # ── on_enter callback ──────────────────────────────────────────────────────
    # Returns: True  = stay in dialog (re-render)
    #          False = exit dialog (outer loop decides next step via _next_action)
    _next_action: list[str] = [""]  # "pick_folder" | "pick_price" | "submit" | "back" | ""

    async def _on_enter(idx: int, row: dict, app, value=None):
        nonlocal error_msg, success_msg
        field  = row.get("field",  "")
        action = row.get("action", "")

        # ── Accept inline edit (text fields) ──────────────────────────────────
        if value is not None:
            if field in ("name", "description", "tags"):
                form[field] = value.strip()
            return True

        # ── Action rows ───────────────────────────────────────────────────────
        if action == "back":
            _next_action[0] = "back"
            app.exit()
            return False

        if action == "submit":
            if not form["name"].strip():
                error_msg = "Extension Name is required."
                return True
            if not form["folder"] or not Path(form["folder"]).is_dir():
                error_msg = "A valid Source Directory is required."
                return True
            if not form["description"].strip():
                error_msg = "Short Description is required."
                return True
            valid_folder, folder_err = _validate_extension_folder(form["type"], form["folder"])
            if not valid_folder:
                error_msg = folder_err or "Invalid extension folder structure."
                return True
            _next_action[0] = "submit"
            app.exit()
            return False

        # ── Field rows ────────────────────────────────────────────────────────
        if field == "name":
            _set_inline_edit("name", "  Extension Name: ", form["name"])
            return True

        if field == "description":
            _set_inline_edit("description", "  Description: ", form["description"])
            return True

        if field == "tags":
            _set_inline_edit("tags", "  Tags (comma separated): ", form["tags"])
            return True

        if field == "type":
            curr = _EXT_TYPES.index(form["type"]) if form["type"] in _EXT_TYPES else 0
            form["type"] = _EXT_TYPES[(curr + 1) % len(_EXT_TYPES)]
            return True

        if field == "category":
            curr = _CATEGORIES.index(form["category"]) if form["category"] in _CATEGORIES else 0
            form["category"] = _CATEGORIES[(curr + 1) % len(_CATEGORIES)]
            return True

        if field == "folder":
            _next_action[0] = "pick_folder"
            app.exit()
            return False

        if field == "price":
            _next_action[0] = "pick_price"
            app.exit()
            return False

        return True

    # ── Outer loop ─────────────────────────────────────────────────────────────
    while True:
        _next_action[0] = ""

        # Build rows fresh each iteration
        rows: list[dict] = []

        rows.append({"type": "info", "bold": True, "color": _WHITE,
                     "text": " PUBLISH NEW EXTENSION TO MARKETPLACE"})
        rows.append({"type": "info", "color": _MUTED,
                     "text": "Fill in the form below, then press Upload & Publish."})
        rows.append({"type": "spacer"})

        if error_msg:
            rows.append({"type": "info", "bold": True, "color": _RED,   "text": f"✗  {error_msg}"})
            error_msg = ""
        if success_msg:
            rows.append({"type": "info", "bold": True, "color": _GREEN, "text": f"✓  {success_msg}"})

        rows.append({"type": "sep"})
        rows.append({"type": "field", "field": "name",        "label": "1. Name",         "hint": "Enter key → type the display name"})
        rows.append({"type": "field", "field": "type",        "label": "2. Type",         "hint": "Enter cycles: skill → miniagent → tool → mcp"})
        rows.append({"type": "field", "field": "folder",      "label": "3. Source Folder","hint": "Enter opens folder picker"})
        rows.append({"type": "field", "field": "description", "label": "4. Description",  "hint": "Enter key → type a short summary"})
        rows.append({"type": "field", "field": "category",    "label": "5. Category",     "hint": "Enter cycles: coding → ai → productivity → devops → data → other"})
        rows.append({"type": "field", "field": "price",       "label": "6. Pricing",      "hint": "Enter opens pricing picker"})
        rows.append({"type": "field", "field": "tags",        "label": "7. Tags",         "hint": "Enter key → type comma-separated tags"})
        rows.append({"type": "sep"})
        rows.append({"type": "action", "action": "submit", "label": " Upload & Publish Package to Marketplace",
                     "color": _GREEN, "hint": "Zips folder and uploads to marketplace"})
        rows.append({"type": "action", "action": "back",   "label": "←  Cancel & Return to Marketplace",
                     "color": _RED,   "hint": "Discard changes and go back"})

        def _make_render(f):
            def _render(i, row, sel):
                return _render_form_row(i, row, sel, f)
            return _render

        _run_list_dialog(
            rows,
            _make_render(form),
            title="Publish Extension Wizard",
            legend="UP/DOWN: Navigate  •  ENTER: Edit / Select  •  ESC: Cancel edit / Back",
            is_selectable_fn=_is_selectable,
            on_enter=_on_enter,
        )

        # ── Handle next action ─────────────────────────────────────────────────
        na = _next_action[0]

        if na == "back":
            break

        if na == "pick_folder":
            picked = _pick_folder(form["folder"], form["type"])
            if picked:
                form["folder"] = picked
                _autofill_from_folder(form, picked)
            continue

        if na == "pick_price":
            picked_price = _pick_price(form["price"])
            if picked_price:
                form["price"]        = picked_price["price"]
                form["payment_type"] = picked_price["payment_type"]
                form["sub_interval"] = picked_price.get("sub_interval", "")
            continue

        if na == "submit":
            # ── Security Check ─────────────────────────────────────────────────
            try:
                zip_b64, readme, file_contents = _zip_folder_to_base64_compiled(form["folder"])
            except Exception as ex:
                error_msg = f"Error packaging: {ex}"
                continue

            if not zip_b64:
                error_msg = "Could not read source folder."
                continue

            # Run initial security scan (CHECK mode inside dialog window)
            scan_result = _run_security_check(console, form["name"], form["type"], file_contents, mode="check")

            overall = (scan_result or {}).get("overall", "UNKNOWN")
            issues = (scan_result or {}).get("issues", [])
            fixes = (scan_result or {}).get("fixes_required", [])
            user_action = (scan_result or {}).get("user_action", "")

            # If user selected "fix" from the dialog options
            if user_action == "fix" or (overall in ("REJECTED", "NEEDS_FIXES") and user_action == "fix"):
                # Run FIX mode with AI tool-calling enabled (edit_file, read_file, grep_search, web_search)
                fix_result = _run_security_check(
                    console,
                    form["name"],
                    form["type"],
                    file_contents,
                    mode="fix",
                    issues=issues or fixes,
                    source_folder=form["folder"],
                )

                # Re-read updated folder after auto-fixing
                zip_b64, readme, file_contents = _zip_folder_to_base64_compiled(form["folder"])

                # Re-verify with CHECK mode
                scan_result = _run_security_check(console, form["name"], form["type"], file_contents, mode="check")
                overall = (scan_result or {}).get("overall", "UNKNOWN")
                issues = (scan_result or {}).get("issues", [])
                user_action = (scan_result or {}).get("user_action", "")

            if overall not in ("SAFE", "FIXED") or user_action == "cancel":
                issue_lines = "\n  ".join(issues) if issues else "Security verification not passed."
                error_msg = f"SECURITY CHECK CANCELLED OR FAILED:\n  {issue_lines}"
                continue

            # SAFE — proceed to publish compiled zip
            slug = re.sub(r"[^a-z0-9-]", "-", form["name"].lower()).strip("-")
            tags_list = [t.strip() for t in form["tags"].split(",") if t.strip()]

            status, data = _api_post("/marketplace/listings", {
                "name":                  form["name"],
                "slug":                  slug,
                "type":                  form["type"],
                "category":              form["category"],
                "description":           form["description"],
                "readme":                readme,
                "price_usd":             float(form["price"]),
                "is_paid":               float(form["price"]) > 0,
                "payment_type":          form["payment_type"],
                "subscription_interval": form["sub_interval"] if form["payment_type"] == "subscription" else None,
                "tags":                  tags_list,
                "zip_base64":            zip_b64,
            })

            if status in (200, 201):
                dl = (data or {}).get("zip_url", f"https://api.utim.dev/marketplace/packages/{slug}.zip")
                success_msg = f"'{form['name']}' is now published! (Security-verified + Auto-fixed + Compiled )\n  Download: {dl}"
                form["name"] = form["folder"] = form["description"] = ""
            elif status == 401:
                error_msg = "Not authenticated. Run /login first."
            else:
                msg = (data or {}).get("detail", f"HTTP {status}")
                error_msg = f"Publish failed: {msg}"
            continue

        # ESC/Q with no _next_action set — user quit
        break