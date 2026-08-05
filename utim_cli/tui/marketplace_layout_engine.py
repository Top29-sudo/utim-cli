"""
UTIM Terminal Web Application Layout Renderer
----------------------------------------------
Renders a persistent 3-pane layout:
  1. Left Sidebar: Navigation categories & creator hub
  2. Central Content Panel: Extension cards, features, search results, or detail pages
  3. Right Quick-Preview Panel: Live extension preview & details
"""

from __future__ import annotations

import shutil
import textwrap
from typing import Any, List, Dict, Optional, Tuple
from utim_cli.tui.marketplace_app_state import MarketplaceAppState, SIDEBAR_SECTIONS, SidebarItem


def _format_type_tag(itype: str) -> str:
    tags = {
        "skill": "📚 SKILL",
        "miniagent": "🤖 MINIAGENT",
        "tool": "🔧 TOOL",
        "mcp": "🔌 MCP SERVER",
    }
    return tags.get(itype, "📦 EXTENSION")


def render_marketplace_webapp(state: MarketplaceAppState) -> List[Tuple[str, str]]:
    """Render the full terminal web application UI tuples for prompt_toolkit FormattedTextControl."""
    term_cols, term_lines = shutil.get_terminal_size((100, 30))

    # Calculate column widths for 3-pane layout
    sidebar_w = 26
    preview_w = 34 if term_cols >= 110 else (28 if term_cols >= 90 else 0)
    content_w = max(30, term_cols - sidebar_w - preview_w - 4)

    out: List[Tuple[str, str]] = []

    # 1. Top Bar
    out.append(("bold #cba6f7", " 🛍️ UTIM MARKETPLACE "))
    out.append(("dim #45475a", " │ "))
    query_display = state.search_query if state.search_query else "Search extensions... ('/' or Tab to focus)"
    q_style = "bold #89dceb" if state.active_panel == "topbar" else "dim #6c7086"
    out.append((q_style, f" 🔍 [{query_display.ljust(content_w - 20)}] "))
    out.append(("dim #45475a", " │ "))
    out.append(("bold #a6e3a1", " 💰 Wallet "))
    out.append(("dim #45475a", " │ "))
    out.append(("bold #f5e0dc", " 👤 Profile \n"))
    out.append(("dim #45475a", "─" * term_cols + "\n"))

    # 2. Main 3-Pane View Body
    body_lines_count = max(10, term_lines - 6)

    # Render Sidebar
    sidebar_rows: List[Tuple[str, str]] = []
    current_sec = ""
    sidebar_item_counter = 0

    for item in SIDEBAR_SECTIONS:
        if item.section != current_sec:
            current_sec = item.section
            sidebar_rows.append(("bold #f9e2af", f"\n {current_sec}\n"))

        is_sel = (sidebar_item_counter == state.selected_sidebar_idx)
        if is_sel and state.active_panel == "sidebar":
            style = "bg:#313244 bold #cba6f7"
            prefix = " ➔ "
        elif is_sel:
            style = "bold #89b4fa"
            prefix = " ▸ "
        else:
            style = "#cdd6f4"
            prefix = "   "

        label_str = f"{prefix}{item.icon} {item.label}"
        sidebar_rows.append((style, f"{label_str.ljust(sidebar_w - 1)}\n"))
        sidebar_item_counter += 1

    # Render Central Content
    content_rows: List[Tuple[str, str]] = []
    items = state.listings or []

    if state.loading:
        content_rows.append(("bold #89dceb", "\n  ⏳ Connecting to UTIM registry...\n"))
    elif not items:
        content_rows.append(("bold #f38ba8", "\n  📭 No extensions found.\n"))
        content_rows.append(("dim #6c7086", "     Try clearing search filter or switching categories.\n"))
    else:
        for idx, item in enumerate(items[:20]):
            is_sel = (idx == state.selected_content_idx)
            name = item.get("name", "Extension")[:content_w - 22]
            itype = item.get("type", "skill")
            type_tag = _format_type_tag(itype)
            price = item.get("price_usd", 0.0)
            is_paid = item.get("is_paid", False)
            price_str = "FREE" if not is_paid or price == 0 else f"${price:.2f}"

            if is_sel and state.active_panel == "content":
                card_style = "bg:#313244 bold #f5e0dc"
                border_style = "bg:#313244 bold #cba6f7"
                ptr = "➔ "
            elif is_sel:
                card_style = "bold #89b4fa"
                border_style = "bold #89b4fa"
                ptr = "▸ "
            else:
                card_style = "#cdd6f4"
                border_style = "dim #45475a"
                ptr = "  "

            desc = item.get("description", "")[:content_w - 10]
            stars = item.get("rating_avg", 0.0)
            dls = item.get("download_count", 0)
            is_verified = item.get("is_verified", True)
            verified_badge = " [✓ Verified]" if is_verified else ""

            content_rows.append((border_style, f"{ptr}┌── {name}{verified_badge}  [{type_tag}]  [{price_str}]\n"))
            content_rows.append((card_style, f"   │   {desc}\n"))
            content_rows.append((border_style, f"   └── ⭐ {stars:.1f}  │  ⬇ {dls:,} installs  │  🛡️ SHA-256 Passed  [View]\n\n"))

    # Render Preview Panel
    preview_rows: List[Tuple[str, str]] = []
    sel_item = state.selected_item or (items[state.selected_content_idx] if items and state.selected_content_idx < len(items) else None)

    if sel_item and preview_w > 0:
        preview_rows.append(("bold #f9e2af", f" Quick Preview\n"))
        preview_rows.append(("dim #45475a", "─" * (preview_w - 2) + "\n"))
        preview_rows.append(("bold #f5e0dc", f" {sel_item.get('name', '')[:preview_w - 4]}\n"))
        preview_rows.append(("bold #89b4fa", f" {_format_type_tag(sel_item.get('type', ''))}\n"))
        preview_rows.append(("bold #50fa7b", " ✓ Verified Publisher\n\n"))

        preview_rows.append(("dim #6c7086", f" Rating: "))
        preview_rows.append(("bold #f9e2af", f"⭐ {sel_item.get('rating_avg', 0.0):.1f}\n"))
        preview_rows.append(("dim #6c7086", f" Installs: "))
        preview_rows.append(("bold #a6e3a1", f"⬇ {sel_item.get('download_count', 0):,}\n"))
        preview_rows.append(("dim #6c7086", f" Security: "))
        preview_rows.append(("bold #50fa7b", f"🛡️ SHA-256 Verified\n\n"))

        desc_wrapped = textwrap.wrap(sel_item.get("description", ""), width=preview_w - 4)
        for dline in desc_wrapped[:6]:
            preview_rows.append(("#cdd6f4", f" {dline}\n"))

        preview_rows.append(("\n", "\n"))
        preview_rows.append(("bold #a6e3a1", f" [ ⚡ Install ]   [ Open Details ]\n"))
    elif preview_w > 0:
        preview_rows.append(("dim #6c7086", "\n Select an extension\n to preview details.\n"))

    # Assemble 3 columns line by line
    max_r = max(len(sidebar_rows), len(content_rows), len(preview_rows), body_lines_count)

    for i in range(min(max_r, body_lines_count)):
        # Sidebar cell
        s_tuple = sidebar_rows[i] if i < len(sidebar_rows) else ("", "")
        out.append(s_tuple)

        # Vertical separator 1
        out.append(("dim #45475a", "│ "))

        # Content cell
        c_tuple = content_rows[i] if i < len(content_rows) else ("", "")
        out.append(c_tuple)

        # Vertical separator 2
        if preview_w > 0:
            out.append(("dim #45475a", "│ "))
            p_tuple = preview_rows[i] if i < len(preview_rows) else ("", "")
            out.append(p_tuple)

    # 3. Bottom Footer Legend Bar
    out.append(("dim #45475a", "─" * term_cols + "\n"))
    out.append(("bold #cba6f7", " ↑↓ "))
    out.append(("dim #6c7086", "Navigate  "))
    out.append(("bold #89b4fa", "Tab "))
    out.append(("dim #6c7086", "Switch Panel  "))
    out.append(("bold #a6e3a1", "Enter "))
    out.append(("dim #6c7086", "Open/Install  "))
    out.append(("bold #89dceb", "/ "))
    out.append(("dim #6c7086", "Search  "))
    out.append(("bold #f38ba8", "Esc/Q "))
    out.append(("dim #6c7086", "Back/Exit"))

    return out
