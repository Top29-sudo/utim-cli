import time

CATEGORIES = {
    "Miniagent Tools": {
        "pattern": lambda name: name.startswith("miniagent_"),
        "icon": "",
    },
    "File Operations & Editing": {
        "pattern": lambda name: name in ("read_file", "write_file", "edit_file", "replace_file_content", "multi_replace_file_content", "move_file", "delete_file", "list_directory", "view_file", "grep_search"),
        "icon": "",
    },
    "Command & System Exec": {
        "pattern": lambda name: name in ("run_command", "get_background_output", "send_background_input", "stop_background_process", "list_background_processes"),
        "icon": "",
    },
    "Web & Image AI": {
        "pattern": lambda name: name in ("web_search", "generate_image", "analyze_image"),
        "icon": "",
    },
    "Project & Code Semantics": {
        "pattern": lambda name: name in ("plan_project", "manage_todos"),
        "icon": "",
    },
    "Blender & 3D Tools": {
        "pattern": lambda name: name.startswith("blender_"),
        "icon": "",
    },
    "Model Context Protocol (MCP)": {
        "pattern": lambda name: False,
        "icon": "",
    }
}

def get_category_for_tool(name, is_mcp=False):
    if is_mcp:
        return "Model Context Protocol (MCP)"
    for cat_name, cat_info in CATEGORIES.items():
        if cat_info["pattern"](name):
            return cat_name
    return "Miscellaneous & Utilities"

def _dialog_tools(orchestrator):
    """Interactive dialog to enable or disable tools to manage prompt context usage."""
    from utim_cli.tools import get_tools
    from utim_cli.config import config
    from utim_cli.utim import console, _run_list_dialog
    
    utim_tools, _ = get_tools(include_disabled=True)
    
    while True:
        # Load disabled tools list
        disabled_tools = config.get("disabled_tools") or []
        if not isinstance(disabled_tools, list):
            disabled_tools = []

        # Re-fetch dynamic tools each loop pass including disabled tools
        utim_tools, _ = get_tools(include_disabled=True)
        
        # Gather all tools
        mcp_tools = []
        try:
            from utim_cli.mcp_client import mcp_manager
            mcp_tools = mcp_manager.get_tools()
        except Exception:
            pass
            
        # Group tools by category
        grouped_tools = {
            "Miniagent Tools": [],
            "File Operations & Editing": [],
            "Command & System Exec": [],
            "Web & Image AI": [],
            "Project & Code Semantics": [],
            "Blender & 3D Tools": [],
            "Model Context Protocol (MCP)": [],
            "Miscellaneous & Utilities": []
        }
        
        for t in utim_tools:
            name = t["function"]["name"]
            cat = get_category_for_tool(name, is_mcp=False)
            grouped_tools[cat].append(t)
            
        for t in mcp_tools:
            name = t["function"]["name"]
            cat = get_category_for_tool(name, is_mcp=True)
            grouped_tools[cat].append(t)
            
        rows = []
        # Add special action options
        rows.append({
            "name": "   Enable All Tools",
            "desc": "Turn on all built-in and MCP tools",
            "action": "enable_all"
        })
        rows.append({
            "name": "   Disable All Tools",
            "desc": "Turn off all built-in and MCP tools",
            "action": "disable_all"
        })
        rows.append({
            "name": "   Exit and Save Changes",
            "desc": "Return to the chat screen",
            "action": "exit"
        })
        
        # Build list rows with categories
        for cat_name, cat_tools in grouped_tools.items():
            if not cat_tools:
                continue
                
            # Determine status of the category
            total_count = len(cat_tools)
            enabled_tools_in_cat = [t for t in cat_tools if t["function"]["name"] not in disabled_tools]
            enabled_count = len(enabled_tools_in_cat)
            
            if enabled_count == total_count:
                status = "all_enabled"
                checkbox = "☑"
            elif enabled_count == 0:
                status = "all_disabled"
                checkbox = "☐"
            else:
                status = "partially_enabled"
                checkbox = "☒"
                
            # Category header toggle row
            rows.append({
                "name": f"{checkbox}  Category: {cat_name} ({enabled_count}/{total_count} enabled)",
                "desc": f"Toggle all tools under {cat_name}",
                "category_name": cat_name,
                "action": "toggle_category",
                "status": status,
                "tool_names": [t["function"]["name"] for t in cat_tools]
            })
            
            # Indented tools belonging to the category
            for t in cat_tools:
                name = t["function"]["name"]
                desc = t["function"]["description"]
                is_enabled = name not in disabled_tools
                checkbox = "☑" if is_enabled else "☐"
                name_display = f"   {checkbox}  {name}"
                rows.append({
                    "name": name_display,
                    "desc": desc,
                    "tool_name": name,
                    "action": "toggle",
                    "category_name": cat_name,
                    "is_enabled": is_enabled
                })
                
        def render_row(idx, row, selected):
            bg = 'bg:#313244' if selected else ''
            act = row.get("action")
            
            if act == "exit":
                fg = 'bold fg:#b4befe'
                desc_padding = "      "
            elif act == "enable_all":
                fg = 'bold fg:#a6e3a1'
                desc_padding = "      "
            elif act == "disable_all":
                fg = 'bold fg:#f38ba8'
                desc_padding = "      "
            elif act == "toggle_category":
                st = row.get("status")
                if st == "all_enabled":
                    fg = 'bold fg:#a6e3a1'
                elif st == "all_disabled":
                    fg = 'bold fg:#f38ba8'
                else:
                    fg = 'bold fg:#f9e2af'
                desc_padding = "      "
            else:
                # Indented tool toggle row
                is_checked = row.get("is_enabled", False)
                fg = 'bold fg:#a6e3a1' if is_checked else 'fg:#6c7086'
                desc_padding = "         "
                
            import textwrap
            import shutil

            term_w = shutil.get_terminal_size().columns
            left_space_len = 4 + len(desc_padding)
            wrap_width = max(20, term_w - left_space_len - 4)
            desc_lines = textwrap.wrap(row['desc'].replace('\n', ' '), width=wrap_width)
            if not desc_lines:
                desc_lines = [""]
                
            formatted_desc = ""
            for line in desc_lines:
                formatted_desc += f"{desc_padding}{line}\n"

            desc_style = 'fg:#9399b2'
            return [
                (bg, '  ➔ ' if selected else '    '),
                (fg, f"{row['name']}\n"),
                (desc_style, formatted_desc)
            ]
            
        action, idx = _run_list_dialog(
            rows,
            render_row,
            title="UTIM Tools Selection Menu  [dim](Choose which tools/categories are enabled)[/dim]",
            legend="Use UP/DOWN/J/K to navigate, ENTER to toggle/execute, ESC/Q to save and exit"
        )
        
        if action != "select":
            break
            
        selected_row = rows[idx]
        act = selected_row.get("action")
        
        if act == "exit":
            break
        elif act == "enable_all":
            all_names = [t["function"]["name"] for t in utim_tools] + [t["function"]["name"] for t in mcp_tools]
            disabled_tools = []
            config.set("disabled_tools", disabled_tools)
        elif act == "disable_all":
            all_names = [t["function"]["name"] for t in utim_tools] + [t["function"]["name"] for t in mcp_tools]
            config.set("disabled_tools", all_names)
        elif act == "toggle_category":
            tool_names = selected_row["tool_names"]
            status = selected_row["status"]
            
            # If all are enabled, we disable all of them
            if status == "all_enabled":
                for t_name in tool_names:
                    if t_name not in disabled_tools:
                        disabled_tools.append(t_name)
            # If all are disabled or partially enabled, we enable all of them
            else:
                for t_name in tool_names:
                    if t_name in disabled_tools:
                        disabled_tools.remove(t_name)
                        
            config.set("disabled_tools", disabled_tools)
        elif act == "toggle":
            tool_name = selected_row["tool_name"]
            if tool_name in disabled_tools:
                disabled_tools.remove(tool_name)
            else:
                disabled_tools.append(tool_name)
            config.set("disabled_tools", disabled_tools)
            
    console.print("\n  [bold green]✓ Tools configuration updated successfully.[/bold green]\n")
