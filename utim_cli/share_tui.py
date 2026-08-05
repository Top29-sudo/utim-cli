import os
import subprocess
from typing import List, Optional
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.application import run_in_terminal

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from utim_cli.share import ShareManager, EXCLUDE_OPTIONS, EXPIRY_OPTIONS, ShareRecord
from utim_cli.constants import ARROW_SYMBOL

import sys
theme_console = Console(file=sys.__stdout__)

def copy_to_clipboard(text: str) -> bool:
    """Helper to copy text to clipboard using clip.exe on Windows."""
    try:
        process = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
        process.communicate(input=text.encode('utf-8'))
        return process.returncode == 0
    except Exception:
        return False

def _safe_exit(app, result=None):
    if not app.is_done:
        try:
            app.exit(result)
        except Exception:
            pass

def _run_checkbox_dialog(items, title="", legend=""):
    """
    Checklist dialog using prompt_toolkit.
    Allows toggling options with SPACE and accepting with ENTER.
    """
    sel = [0]
    selected_keys = set(item["key"] for item in items)  # Pre-select all by default
    N = len(items)
    act = [None]

    def content():
        out = []
        out.append(('bold #42bcf5', f'\n  {title}\n'))
        out.append(('class:dim',    f'  {legend}\n\n'))

        for i, item in enumerate(items):
            is_selected = item["key"] in selected_keys
            highlighted = i == sel[0]
            
            bg = 'bg:#1a3a2a bold #cdd6f4' if highlighted else ''
            check = ' [x] ' if is_selected else ' [ ] '
            check_style = 'bold #a6e3a1' if is_selected else 'class:dim fg:#f38ba8'
            if highlighted:
                check_style = 'bold bg:#1a3a2a'
                
            out.extend([
                (bg or check_style, check),
                (bg or 'bold #cdd6f4', f"{item['name'].ljust(20)}"),
                (bg or 'class:dim', f"— {item['desc']}\n")
            ])
        out.append(('', '\n'))
        return out

    kb = KeyBindings()

    @kb.add('up')
    @kb.add('k')
    def _up(e):
        sel[0] = (sel[0] - 1) % N
        e.app.invalidate()

    @kb.add('down')
    @kb.add('j')
    def _dn(e):
        sel[0] = (sel[0] + 1) % N
        e.app.invalidate()

    @kb.add('space')
    def _toggle(e):
        key = items[sel[0]]["key"]
        if key in selected_keys:
            selected_keys.remove(key)
        else:
            selected_keys.add(key)
        e.app.invalidate()

    @kb.add('enter')
    def _enter(e):
        act[0] = 'select'
        _safe_exit(e.app)

    @kb.add('escape')
    @kb.add('q')
    @kb.add('c-c')
    def _quit(e):
        _safe_exit(e.app)

    dialog_app = Application(
        layout=Layout(Window(
            FormattedTextControl(content),
            wrap_lines=False,
        )),
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({'dim': '#555577', '': 'bg:#0d0d16 fg:#cdd6f4'}),
        mouse_support=False,
    )
    dialog_app.run()
    
    if act[0] == 'select':
        return list(selected_keys)
    return None

def _run_custom_omits_dialog(workspace_path: str) -> Optional[List[str]]:
    """
    Text area input dialog using prompt_toolkit for custom exclusions.
    Validates that paths are within the workspace root.
    Returns list of paths or None if cancelled.
    """
    from prompt_toolkit.widgets import TextArea, Frame
    import pathlib
    
    ws_path = pathlib.Path(workspace_path).resolve()
    
    text_area = TextArea(
        multiline=False,
        password=False,
        focus_on_click=True,
    )
    
    act = [None]
    error_msg = [""]
    
    def get_prompt_text():
        out = []
        out.append(('bold #42bcf5', '\n  📤 Step 3: Enter Custom Files/Folders to Omit (Optional)\n'))
        out.append(('class:dim',    '  Type or paste any path relative to the root folder (e.g. package-lock.json, data/logs).\n'))
        out.append(('class:dim',    '  Path MUST be inside the current root folder\'s file tree.\n'))
        out.append(('class:dim',    '  Separate multiple paths with commas. Press ENTER to submit, ESC to cancel/skip.\n\n'))
        if error_msg[0]:
            out.append(('bold red', f'  ✗ Error: {error_msg[0]}\n\n'))
        return out

    kb = KeyBindings()

    @kb.add('enter')
    def _enter(e):
        val = text_area.text.strip()
        if not val:
            act[0] = 'submit'
            _safe_exit(e.app)
            return
            
        parts = [p.strip() for p in val.split(",") if p.strip()]
        for part in parts:
            try:
                if not part:
                    continue
                p = pathlib.Path(part).expanduser()
                if p.is_absolute():
                    resolved = p.resolve()
                else:
                    resolved = (ws_path / p).resolve()
                
                # Check if it is a descendant of workspace_path
                is_inside = (ws_path == resolved) or (ws_path in resolved.parents)
                if not is_inside:
                    error_msg[0] = f"Path '{part}' is outside the root folder!"
                    return
            except Exception:
                error_msg[0] = f"Invalid path format: '{part}'"
                return
                
        act[0] = 'submit'
        _safe_exit(e.app)

    @kb.add('escape')
    @kb.add('c-c')
    def _quit(e):
        _safe_exit(e.app)

    layout = Layout(HSplit([
        Window(FormattedTextControl(get_prompt_text), height=6),
        Frame(text_area, title="Custom Exclude Paths"),
    ]))

    dialog_app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({
            'dim': '#555577',
            '': 'bg:#0d0d16 fg:#cdd6f4',
            'frame.border': '#89b4fa',
        }),
        mouse_support=True,
    )
    dialog_app.run()
    
    if act[0] == 'submit':
        val = text_area.text.strip()
        if not val:
            return []
        return [p.strip() for p in val.split(",") if p.strip()]
    return None

def _run_share_type_dialog():
    """Selection list for picking the share type."""
    options = [
        {"key": "project", "label": "Share Project", "desc": "Zips the workspace excluding omitted files"},
        {"key": "chat_project", "label": "Share Chat & Project", "desc": "Zips the workspace + chat history"},
        {"key": "chat", "label": "Share Chat", "desc": "Zips the chat history only"}
    ]
    sel = [0]
    N = len(options)
    act = [None]

    def content():
        out = []
        out.append(('bold #42bcf5', '\n  📤 Step 1: Choose Share Type\n'))
        out.append(('class:dim',    '  Select what content you would like to package and share:\n\n'))

        for i, opt in enumerate(options):
            highlighted = i == sel[0]
            bg = 'bg:#1a3a2a bold #cdd6f4' if highlighted else ''
            bullet = f'{ARROW_SYMBOL} ' if highlighted else '• '
            bullet_style = 'bold #42bcf5' if highlighted else 'class:dim'
            
            out.extend([
                (bg or bullet_style, f"  {bullet}"),
                (bg or 'bold #cdd6f4', f"{opt['label'].ljust(25)}"),
                (bg or 'class:dim', f"— {opt['desc']}\n")
            ])
        out.append(('', '\n'))
        return out

    kb = KeyBindings()

    @kb.add('up')
    @kb.add('k')
    def _up(e):
        sel[0] = (sel[0] - 1) % N
        e.app.invalidate()

    @kb.add('down')
    @kb.add('j')
    def _dn(e):
        sel[0] = (sel[0] + 1) % N
        e.app.invalidate()

    @kb.add('enter')
    def _enter(e):
        act[0] = options[sel[0]]["key"]
        _safe_exit(e.app)

    @kb.add('escape')
    @kb.add('q')
    @kb.add('c-c')
    def _quit(e):
        _safe_exit(e.app)

    dialog_app = Application(
        layout=Layout(Window(
            FormattedTextControl(content),
            wrap_lines=False,
        )),
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({'dim': '#555577', '': 'bg:#0d0d16 fg:#cdd6f4'}),
        mouse_support=False,
    )
    dialog_app.run()
    return act[0]

def _run_expiry_dialog(options, title="", legend=""):
    """Simple selection list for picking the link expiry duration."""
    sel = [0]
    N = len(options)
    act = [None]

    def content():
        out = []
        out.append(('bold #42bcf5', f'\n  {title}\n'))
        out.append(('class:dim',    f'  {legend}\n\n'))

        for i, opt in enumerate(options):
            highlighted = i == sel[0]
            bg = 'bg:#1a3a2a bold #cdd6f4' if highlighted else ''
            bullet = f'{ARROW_SYMBOL} ' if highlighted else '• '
            bullet_style = 'bold #42bcf5' if highlighted else 'class:dim'
            
            out.extend([
                (bg or bullet_style, f"  {bullet}"),
                (bg or 'bold #cdd6f4', f"{opt['label']}\n")
            ])
        out.append(('', '\n'))
        return out

    kb = KeyBindings()

    @kb.add('up')
    @kb.add('k')
    def _up(e):
        sel[0] = (sel[0] - 1) % N
        e.app.invalidate()

    @kb.add('down')
    @kb.add('j')
    def _dn(e):
        sel[0] = (sel[0] + 1) % N
        e.app.invalidate()

    @kb.add('enter')
    def _enter(e):
        act[0] = 'select'
        _safe_exit(e.app)

    @kb.add('escape')
    @kb.add('q')
    @kb.add('c-c')
    def _quit(e):
        _safe_exit(e.app)

    dialog_app = Application(
        layout=Layout(Window(
            FormattedTextControl(content),
            wrap_lines=False,
        )),
        key_bindings=kb,
        full_screen=True,
        style=PTStyle.from_dict({'dim': '#555577', '': 'bg:#0d0d16 fg:#cdd6f4'}),
        mouse_support=False,
    )
    dialog_app.run()
    
    if act[0] == 'select':
        return options[sel[0]]
    return None

def _run_shares_dashboard(manager: ShareManager):
    """
    Searchable dashboard showing existing shares, remaining time, delete options,
    and a top option for creating a new share.
    """
    current_raw_rows = []
    filtered_rows = []
    N_filtered = [0]
    sel = [0]
    act = [None]
    viewport_start = [0]

    def update_filtered_rows(query):
        nonlocal filtered_rows
        q = query.strip().lower()
        if not q:
            filtered_rows = list(enumerate(current_raw_rows))
        else:
            filtered_rows = []
            for idx, row in enumerate(current_raw_rows):
                if row["type"] == "new":
                    filtered_rows.append((idx, row))
                else:
                    rec = row["record"]
                    if (q in str(rec.name or '').lower() or 
                        q in str(rec.id or '').lower() or 
                        q in str(rec.link or '').lower() or 
                        any(q in str(excl or '').lower() for excl in rec.excluded)):
                        filtered_rows.append((idx, row))
        N_filtered[0] = len(filtered_rows)
        if N_filtered[0] > 0:
            sel[0] = min(sel[0], N_filtered[0] - 1)
        else:
            sel[0] = 0
        viewport_start[0] = min(viewport_start[0], sel[0])

    def update_rows():
        records = manager.get_all()
        raw_rows = [{"type": "new"}]
        for r in records:
            raw_rows.append({"type": "record", "record": r})
        nonlocal current_raw_rows
        current_raw_rows = raw_rows
        update_filtered_rows(search_field.text)

    def get_row_height(row):
        return 3 if row["type"] == "new" else 5

    def content():
        import shutil
        term_h = shutil.get_terminal_size().lines
        
        # 10 lines budget for frame, search, legend, spacing
        available_height = max(5, term_h - 10)
        
        if N_filtered[0] == 0:
            return [
                ('', '\n'),
                ('bold #f38ba8', '    ⚠️  No matching shared items found.\n'),
            ]

        matching_heights = [get_row_height(row) for _, row in filtered_rows]

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
            highlighted = i == sel[0]
            bg = 'bg:#1a3a2a bold #cdd6f4' if highlighted else ''
            
            if row["type"] == "new":
                out.extend([
                    (bg or 'bold #a6e3a1', "  [+] Share New Link\n"),
                    (bg or 'class:dim', "      Compress workspace and generate a new share link\n\n")
                ])
            else:
                rec = row["record"]
                status = rec.time_remaining()
                status_style = 'bold #a6e3a1' if status != 'Expired' else 'bold #f38ba8'
                if highlighted:
                    status_style = 'bold bg:#1a3a2a'
                
                # Format share type label
                stype = getattr(rec, "share_type", "chat_project")
                if stype == "project":
                    type_label = "Folder"
                elif stype == "chat":
                    type_label = "Chat Only"
                else:
                    type_label = "Folder & Chat"
                
                excl_part = f"Excluded: {', '.join(rec.excluded) if rec.excluded else 'none'}"
                
                if highlighted:
                    action_bar = f"   {ARROW_SYMBOL} [ Details (Enter) ]   [ Delete (Ctrl+D) ]"
                    action_style = "bold #89b4fa bg:#1a3a2a"
                else:
                    action_bar = "     [ Details ]           [ Delete ]"
                    action_style = "class:dim"
                
                out.extend([
                    (bg or 'bold #cdd6f4', f"  📁  {rec.name} "),
                    (bg or 'class:dim', f"({rec.id})"),
                    (bg or 'bold #cba6f7', f" [{type_label}]"),
                    (bg or status_style, f" [{status}]".rjust(15) + "\n"),
                    (bg or 'class:dim fg:#89d5fa', f"      {rec.link}\n"),
                    (bg or 'class:dim', f"      {excl_part}\n"),
                    (action_style, f"{action_bar}\n\n")
                ])

        remaining = N_filtered[0] - end_idx
        if remaining > 0:
            out.append(('class:dim fg:#f9e2af', f'    ▼ ... ({remaining} more below) ... ▼\n'))

        return out

    search_field = TextArea(
        multiline=False,
        prompt=" 🔍 Search Shares: ",
        style="class:search-field",
    )
    search_field.buffer.on_text_changed += lambda buf: update_filtered_rows(buf.text)
    list_control = FormattedTextControl(content, focusable=True)

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

    @kb.add('c-d')
    @kb.add('d', filter=has_focus(list_control))
    def _delete_list(e):
        if N_filtered[0] > 0:
            orig_idx, row = filtered_rows[sel[0]]
            if row["type"] == "record":
                rec = row["record"]
                manager.delete(rec.id)
                update_rows()
                e.app.invalidate()

    @kb.add('enter')
    def _enter(e):
        if N_filtered[0] > 0:
            orig_idx, row = filtered_rows[sel[0]]
            if row["type"] == "new":
                act[0] = ("new", None)
            else:
                act[0] = ("details", row["record"])
            _safe_exit(e.app)

    @kb.add('escape')
    @kb.add('c-c')
    def _quit(e):
        _safe_exit(e.app)

    @kb.add('q', filter=has_focus(list_control))
    def _quit_list(e):
        _safe_exit(e.app)

    title_window = Window(FormattedTextControl([('bold #42bcf5', f'\n  📤  Workspace Share Manager\n')]), height=2)

    search_frame = Frame(search_field, title="Filter Shared Items (Search Name, ID, Link, or Exclusions)")

    list_window = Window(list_control, wrap_lines=False)
    list_frame = Frame(list_window, title="Shared Archives")

    def get_legend():
        if dialog_app.layout.has_focus(search_field):
            return [
                ('bold #a6e3a1', " MODE: SEARCH  "),
                ('class:dim', "—  Type to filter  |  "),
                ('bold #cba6f7', "TAB"),
                ('class:dim', " to switch to list  |  "),
                ('bold #f38ba8', "Ctrl+D"),
                ('class:dim', " to delete selected  |  "),
                ('bold #f38ba8', "ESC"),
                ('class:dim', " to close")
            ]
        else:
            return [
                ('bold #f9e2af', " MODE: SELECT  "),
                ('class:dim', "—  "),
                ('bold #89b4fa', "UP/DOWN / J/K"),
                ('class:dim', " to navigate  |  "),
                ('bold #a6e3a1', "ENTER"),
                ('class:dim', " to select  |  "),
                ('bold #f38ba8', "Ctrl+D/d"),
                ('class:dim', " to delete active link  |  "),
                ('bold #cba6f7', "TAB"),
                ('class:dim', " to search  |  "),
                ('bold #f38ba8', "ESC/Q"),
                ('class:dim', " to close")
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

    update_rows()
    dialog_app.layout.focus(search_field)
    dialog_app.run()

    return act[0]


def wait_for_enter(prompt_text: str = "\n  Press Enter to return..."):
    from prompt_toolkit import prompt
    try:
        prompt(prompt_text)
    except (KeyboardInterrupt, EOFError):
        pass

def show_share_details(record: ShareRecord):
    """Render details of a share record and copy the link to the clipboard."""
    copied = copy_to_clipboard(record.link)
    clipboard_msg = " [green](Copied to clipboard!)[/green]" if copied else " [red](Failed to copy to clipboard)[/red]"
    
    theme_console.print()
    panel = Panel(
        Text.from_markup(
            f"[bold white]📁 Share Package: {record.name}[/bold white]\n\n"
            f"[dim]ID:[/dim]          {record.id}\n"
            f"[dim]Created At:[/dim]  {record.created_at}\n"
            f"[dim]Expires At:[/dim]  {record.expires_at}\n"
            f"[dim]Time Left:[/dim]   {record.time_remaining()}\n"
            f"[dim]Link:[/dim]        [bold cyan]{record.link}[/bold cyan]{clipboard_msg}\n"
            f"[dim]File Path:[/dim]   {record.file_path}\n"
            f"[dim]Excluded:[/dim]    {', '.join(record.excluded) if record.excluded else 'none'}"
        ),
        title="Share Details",
        border_style="#42bcf5",
        expand=False,
        padding=(1, 2)
    )
    theme_console.print(panel)
    wait_for_enter("\n  Press Enter to return to Dashboard...")

def do_create_share(manager: ShareManager, exclude_keys, expiry_hours, chat_messages, share_type):
    """Run zip compression, upload, copy to clipboard, and print status."""
    theme_console.print()
    panel = Panel(
        Text.from_markup(
            "[bold yellow]⚡ Building Share Package...[/bold yellow]\n"
            "[dim]Compressing files and uploading to server...[/dim]"
        ),
        border_style="yellow",
        expand=False,
        padding=(1, 2)
    )
    theme_console.print(panel)
    
    try:
        rec = manager.create_share(exclude_keys, expiry_hours, chat_messages, share_type)
            
        copied = copy_to_clipboard(rec.link)
        clipboard_msg = " [green](Copied to clipboard!)[/green]" if copied else " [red](Failed to copy to clipboard)[/red]"
        
        # Clear screen so final layout fits perfectly
        theme_console.clear()
        
        success_panel = Panel(
            Text.from_markup(
                f"[bold green]✓ Share link created successfully![/bold green]\n\n"
                f"[dim]Link:[/dim] [bold cyan]{rec.link}[/bold cyan]{clipboard_msg}"
            ),
            title="Share Complete",
            border_style="green",
            expand=False,
            padding=(1, 2)
        )
        theme_console.print(success_panel)
    except Exception as e:
        theme_console.print(f"\n[bold red]✗ Failed to create share link: {e}[/bold red]\n")
        
    wait_for_enter("  Press Enter to return...")

def run_share_flow(orchestrator):
    """Main orchestrator for the /share flow."""
    manager = ShareManager()
    
    # Extract chat messages from orchestrator
    chat_messages = getattr(orchestrator, "messages", [])
    
    while True:
        # If there are no shares, go directly to the wizard
        records = manager.get_all()
        if not records:
            # Step 1: select share type
            share_type = _run_share_type_dialog()
            if share_type is None:
                return  # user cancelled
                
            exclude_keys = []
            if share_type in ("project", "chat_project"):
                # Step 2: select exclusions
                exclude_options = EXCLUDE_OPTIONS + [
                    {"key": "add_custom", "name": "[ Add custom files/folders... ]", "desc": "Type or paste a custom file/folder path inside root to omit"}
                ]
                exclude_keys = _run_checkbox_dialog(
                    exclude_options,
                    title="📤 Step 2: Select items to exclude (space to toggle)",
                    legend="Select which files/folders to omit to save space and exclude secrets"
                )
                if exclude_keys is None:
                    return  # user cancelled
                
                if "add_custom" in exclude_keys:
                    exclude_keys.remove("add_custom")
                    custom_omits = _run_custom_omits_dialog(str(manager.workspace_path))
                    if custom_omits is not None:
                        exclude_keys.extend(custom_omits)
                
            # Step 3: select expiry
            expiry_opt = _run_expiry_dialog(
                EXPIRY_OPTIONS,
                title="⏰ Step Choose link expiry duration",
                legend="Select how long the link should remain active before expiring"
            )
            if expiry_opt is None:
                return  # user cancelled
                
            # Step 4: create share
            do_create_share(manager, exclude_keys, expiry_opt["hours"], chat_messages, share_type)
            
            # Since records are no longer empty, we will loop and the dashboard will show next
            continue
            
        # Otherwise, show the dashboard
        action_data = _run_shares_dashboard(manager)
        if not action_data:
            break  # user exited
            
        action, value = action_data
        if action == "new":
            # Run the wizard
            share_type = _run_share_type_dialog()
            if share_type is not None:
                exclude_keys = []
                if share_type in ("project", "chat_project"):
                    exclude_options = EXCLUDE_OPTIONS + [
                        {"key": "add_custom", "name": "[ Add custom files/folders... ]", "desc": "Type or paste a custom file/folder path inside root to omit"}
                    ]
                    exclude_keys = _run_checkbox_dialog(
                        exclude_options,
                        title="📤 Step 2: Select items to exclude (space to toggle)",
                        legend="Select which files/folders to omit to save space and exclude secrets"
                    )
                    if exclude_keys is not None:
                        if "add_custom" in exclude_keys:
                            exclude_keys.remove("add_custom")
                            custom_omits = _run_custom_omits_dialog(str(manager.workspace_path))
                            if custom_omits is not None:
                                exclude_keys.extend(custom_omits)
                if share_type == "chat" or exclude_keys is not None:
                    expiry_opt = _run_expiry_dialog(
                        EXPIRY_OPTIONS,
                        title="⏰ Step Choose link expiry duration",
                        legend="Select how long the link should remain active before expiring"
                    )
                    if expiry_opt is not None:
                        do_create_share(manager, exclude_keys, expiry_opt["hours"], chat_messages, share_type)
        elif action == "details":
            show_share_details(value)
