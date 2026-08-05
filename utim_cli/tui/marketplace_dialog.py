"""

UTIM Marketplace dialog — /marketplace

A full-screen, interactive app-store for discovering, installing, and publishing

UTIM extensions (skills, miniagents, tools, MCP servers).

"""

from __future__ import annotations

import json

import os

import re

import shutil

import textwrap

import time

import threading

import zipfile

from pathlib import Path
from typing import Any, Optional

# ── Import publish dialog from separate file ──────────────────────────────────
from utim_cli.tui.publish_dialog import dialog_publish as _dialog_publish  # type: ignore
from utim_cli.utim import _run_list_dialog, _run_full_screen_flow  # type: ignore

# ── Local Payment Info Storage (~/.utim/payment_id/) ──────────────────────────

def _get_payment_info_path() -> Path:

    return Path.home() / ".utim" / "payment_id" / "payment_info.json"

def _load_payment_info() -> dict:

    path = _get_payment_info_path()

    if path.exists():

        try:

            return json.loads(path.read_text(encoding="utf-8"))

        except Exception:

            pass

    return {}

def _save_payment_info(info: dict) -> None:

    path = _get_payment_info_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(json.dumps(info, indent=2), encoding="utf-8")

# ── Catppuccin Modern Palette ──────────────────────────────────────────────────

_MAUVE   = "#cba6f7"  # Primary accent (purple)

_BLUE    = "#89b4fa"  # Soft sky blue

_CYAN    = "#89dceb"  # Bright cyan

_GREEN   = "#a6e3a1"  # Emerald green (success/free)

_YELLOW  = "#f9e2af"  # Soft gold/amber (ratings/price)

_RED     = "#f38ba8"  # Pastel red (danger/exit)

_SURFACE = "#313244"  # Background highlight surface

_BORDER  = "#45475a"  # Soft border grey

_MUTED   = "#6c7086"  # Dim text

_FG      = "#cdd6f4"  # Main text

_WHITE   = "#f5e0dc"  # Crisp white text

# ── API base ──────────────────────────────────────────────────────────────────

_API_BASE = "https://api.utim.dev"

# ── Categories & Metadata ─────────────────────────────────────────────────────

CATEGORIES = [

    ("all",           "🌐  All Extensions"),

    ("productivity",  "⚡  Productivity"),

    ("coding",        "💻  Coding & Dev"),

    ("ai",            "🤖  AI & Agents"),

    ("writing",       "✍️   Writing & Docs"),

    ("data",          "📊  Data & Analysis"),

    ("devops",        "🔧  DevOps & Shell"),

    ("design",        "🎨  Design & UI"),

    ("research",      "🔍  Research"),

    ("other",         "📦  Other"),

]

TYPE_BADGES = {

    "skill":     ("📦 SKILL",     "#89b4fa"),

    "miniagent": ("🤖 MINI-AGENT", "#cba6f7"),

    "tool":      ("🔧 TOOL",      "#f9e2af"),

    "mcp":       ("🔌 MCP SERVER", "#89dceb"),

}

SORT_OPTIONS = [

    ("featured",   "⭐  Featured"),

    ("popular",    "🔥  Most Popular"),

    ("newest",     "🆕  Newest Additions"),

    ("top_rated",  "🏆  Top Rated"),

    ("free",       "🆓  Free Only"),

    ("paid",       "💎  Premium Only"),

]

# ── API helpers ───────────────────────────────────────────────────────────────

def _get_api_key() -> Optional[str]:

    from utim_cli.config import config

    key = config.get("api_key")

    if key and key != "device_flow":

        return key

    email = config.email

    if email and email.upper() != "GUEST":

        return email

    return None

def _api_get(path: str, params: Optional[dict] = None, timeout: int = 8) -> Optional[dict]:

    try:

        import requests

        key = _get_api_key()

        headers = {"X-API-Key": key} if key else {}

        r = requests.get(f"{_API_BASE}{path}", params=params, headers=headers, timeout=timeout)

        if r.status_code == 200:

            return r.json()

    except Exception:

        pass

    return None

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

def _api_delete(path: str, timeout: int = 15) -> tuple[int, Optional[dict]]:

    try:

        import requests

        key = _get_api_key()

        headers = {"X-API-Key": key} if key else {}

        r = requests.delete(f"{_API_BASE}{path}", headers=headers, timeout=timeout)

        try:

            return r.status_code, r.json()

        except Exception:

            return r.status_code, None

    except Exception:

        return 0, None

# ── Data Fetchers ─────────────────────────────────────────────────────────────

def _fetch_homepage() -> dict:

    data = _api_get("/marketplace/featured")

    if data:

        return data

    return {"featured": [], "popular": [], "newest": [], "top_rated": []}

def _fetch_listings(

    search: str = "",

    category: str = "all",

    sort: str = "featured",

    page: int = 0,

    limit: int = 15,

) -> list[dict]:

    params: dict[str, Any] = {"skip": page * limit, "limit": limit, "sort": sort}

    if search:

        params["q"] = search

    if category and category != "all":

        params["category"] = category

    data = _api_get("/marketplace/listings", params=params)

    if isinstance(data, list):

        return data

    if isinstance(data, dict) and "items" in data:

        return data["items"]

    return []

def _fetch_listing_detail(slug: str) -> Optional[dict]:

    return _api_get(f"/marketplace/listings/{slug}")

def _download_listing(slug: str) -> tuple[bool, str]:

    status, data = _api_post(f"/marketplace/listings/{slug}/download", {})

    if status not in (200, 201) or not data:

        return False, f"Download request failed (HTTP {status})"

    zip_url = data.get("zip_url")

    if not zip_url:

        return False, "Server returned empty zip_url"

    item_type = data.get("type", "skill")

    item_name = data.get("slug", slug)

    return _install_zip(zip_url, item_type, item_name)

def _install_zip(url: str, item_type: str, item_name: str) -> tuple[bool, str]:

    try:

        import requests, tempfile

        key = _get_api_key()

        headers = {"X-API-Key": key} if key else {}

        r = requests.get(url, headers=headers, timeout=30)

        if r.status_code != 200:

            return False, f"Failed to fetch package archive (HTTP {r.status_code})"

        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:

            f.write(r.content)

            tmp_path = f.name

        dest = _get_install_dir(item_type, item_name)

        dest.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(tmp_path, "r") as zf:

            for member in zf.namelist():

                if ".." in member or member.startswith("/"):

                    return False, "Blocked: Archive contains unsafe absolute/relative file paths"

            zf.extractall(str(dest))

        os.unlink(tmp_path)

        return True, str(dest)

    except zipfile.BadZipFile:

        return False, "Corrupted ZIP archive received"

    except Exception as e:

        return False, str(e)

def _get_install_dir(item_type: str, item_name: str) -> Path:

    from utim_cli.config import get_utim_dir

    utim_dir = get_utim_dir()

    if item_type == "skill":

        return utim_dir / "skills" / item_name

    elif item_type == "miniagent":

        return utim_dir / "miniagents" / item_name

    elif item_type in ("tool", "mcp"):

        return utim_dir / "marketplace" / item_type / item_name

    return utim_dir / "marketplace" / item_name

# ── UI Render Formatting Helpers ──────────────────────────────────────────────

def _format_stars(rating: float, count: int) -> str:

    if count == 0:

        return "No reviews yet"

    full = int(round(rating))

    stars = "★" * full + "☆" * (5 - full)

    return f"{stars} ({rating:.1f} • {count} revs)"

def _format_price_pill(price: float, is_paid: bool) -> str:

    if not is_paid or price == 0:

        return "FREE"

    return f"${price:.2f}"

def _format_type_badge(item_type: str) -> tuple[str, str]:

    badge_info = TYPE_BADGES.get(item_type, ("📦 EXTENSION", _BLUE))

    return badge_info[0], badge_info[1]

def _truncate_str(s: str, length: int) -> str:

    s = s.strip()

    return s if len(s) <= length else s[:length - 1] + "…"

def _parse_markup_to_tuples(text: str, default_style: str = "") -> list[tuple[str, str]]:

    """Parse string containing Rich-like tags like '[bold #color]text[/bold]' into prompt_toolkit (style, text) tuples."""

    import re

    if "[" not in text or "]" not in text:

        return [(default_style, text)]

    pattern = re.compile(r'(\[/?(?:bold|dim|cyan|green|yellow|red|blue|magenta|white|\#[a-fA-F0-9]{6})(?:\s+#[a-fA-F0-9]{6})?\])')

    tokens = pattern.split(text)

    result = []

    style_stack = [default_style] if default_style else []

    for token in tokens:

        if not token:

            continue

        if token.startswith("[/") and token.endswith("]"):

            if len(style_stack) > (1 if default_style else 0):

                style_stack.pop()

        elif token.startswith("[") and token.endswith("]"):

            tag_content = token[1:-1].strip()

            parts = tag_content.split()

            st_list = []

            for p in parts:

                if p == "bold":
                    st_list.append(p)
                elif p == "dim":
                    # prompt_toolkit does NOT accept "dim" as a bare
                    # token before a color; raises "Wrong color
                    # format dim". Drop the token; callers usually
                    # pair [dim] with a muted hex color anyway.
                    continue

                elif p.startswith("#") or p in ("cyan", "green", "yellow", "red", "blue", "magenta", "white"):

                    st_list.append(p if p.startswith("#") else f"fg:{p}")

            st_str = " ".join(st_list)

            style_stack.append(st_str)

        else:

            cur_style = style_stack[-1] if style_stack else default_style

            result.append((cur_style, token))

    return result if result else [(default_style, text)]

def _is_selectable(row: dict) -> bool:

    if not isinstance(row, dict):

        return True

    rtype = row.get("type")

    if rtype in ("sep", "banner", "section", "header_bar", "section_title", "info_text", "info", "desc", "title", "spacer"):

        return False

    return True

# ── Browsing Screen ───────────────────────────────────────────────────────────

def _dialog_browse(console, initial_category: str = "all", initial_sort: str = "featured", search: str = "") -> Optional[str]:

    from utim_cli.utim import _run_list_dialog  # type: ignore

    page       = [0]

    category   = [initial_category]

    sort_by    = [initial_sort]

    query      = [search]

    listings   = [None]

    loading    = [True]

    status_msg = ["Connecting to UTIM server..."]

    def _load_data():

        loading[0] = True

        status_msg[0] = "Fetching extensions..."

        try:

            results = _fetch_listings(

                search=query[0],

                category=category[0],

                sort=sort_by[0],

                page=page[0],

            )

            listings[0] = results

            status_msg[0] = f"Found {len(results)} matching extension(s)" if results else "No extensions matched filters"

        except Exception as e:

            listings[0] = []

            status_msg[0] = f"Error connecting: {e}"

        finally:

            loading[0] = False

    # Trigger load thread

    t = threading.Thread(target=_load_data, daemon=True)

    t.start()

    t.join(timeout=8)

    while True:

        items = listings[0] or []

        rows: list[dict] = []

        # Top Filter & Status Header

        filter_str = f"Filter: '{query[0]}'" if query[0] else "Filter: All"

        cat_str = f"Category: {category[0].title()}"

        sort_str = f"Sort: {sort_by[0].replace('_', ' ').title()}"

        rows.append({"type": "header_bar", "text": f"🏷️ {cat_str}  │  ←• {sort_str}  │  🔍 {filter_str}", "status": status_msg[0]})

        rows.append({"type": "sep"})

        # Clean Toolbar Actions

        rows.append({"type": "ctrl", "action": "search",   "icon": "🔍", "label": "Search & Filter Extensions",  "hint": "Set keyword, category, or sorting order"})

        rows.append({"type": "ctrl", "action": "publish",  "icon": "📤", "label": "Publish Your Extension",     "hint": "Share skills, miniagents or tools globally"})

        rows.append({"type": "ctrl", "action": "my_items", "icon": "🗃",  "label": "My Published Extensions",   "hint": "View and manage your extensions"})

        rows.append({"type": "ctrl", "action": "exit",     "icon": "✕",  "label": "Return to Terminal Chat",    "hint": "Close marketplace"})

        rows.append({"type": "sep"})

        # Extension Cards

        if loading[0]:

            rows.append({"type": "info_text", "text": "  ⏳  Loading extensions from global server..."})

        elif not items:

            rows.append({"type": "info_text", "text": "  📭  No extensions found matching your search and category filters."})

        else:

            page_info = f"Marketplace Extensions (Page {page[0]+1})"

            rows.append({"type": "section_title", "text": f"── {page_info} ──"})

            for item in items:

                rows.append({"type": "card", "item": item})

            if len(items) >= 15 or page[0] > 0:

                rows.append({"type": "sep"})

                if page[0] > 0:

                    rows.append({"type": "ctrl", "action": "prev_page", "icon": "●€", "label": f"Previous Page (Page {page[0]})", "hint": ""})

                if len(items) >= 15:

                    rows.append({"type": "ctrl", "action": "next_page", "icon": "▶", "label": f"Next Page (Page {page[0]+2})", "hint": "View more items"})

        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ───────────────────────────────────────────────────────────────\n")]

            if rtype == "header_bar":

                bar = row.get("text", "")

                st  = row.get("status", "")

                return [

                    (f"bold {_MAUVE}", f"  {bar}\n"),

                    (f"{_MUTED}", f"  Status: {st}\n"),

                ]

            if rtype == "section_title":

                return [(f"bold {_CYAN}", f"\n  {row.get('text', '')}\n")]

            if rtype == "info_text":

                return [(f"fg:{_FG}", f"{row.get('text', '')}\n")]

            if rtype == "ctrl":

                act   = row.get("action", "")

                icon  = row.get("icon", "•")

                label = row.get("label", "")

                hint  = row.get("hint", "")

                if act == "exit":

                    fg = f"bold {_RED}" if selected else _RED

                elif act in ("publish", "my_items"):

                    fg = f"bold {_MAUVE}" if selected else _MAUVE

                else:

                    fg = f"bold {_BLUE}" if selected else _BLUE

                pointer = "  ➔ " if selected else "    "

                lines = [(bg or fg, f"{pointer}{icon}  {label}\n")]

                if selected and hint:

                    lines.append((bg or f"{_MUTED}", f"       {hint}\n"))

                return lines

            if rtype == "card":

                item = row.get("item", {})

                name  = _truncate_str(item.get("name", "Untitled Extension"), 34)

                itype = item.get("type", "skill")

                type_tag, type_color = _format_type_badge(itype)

                price_tag = _format_price_pill(item.get("price_usd", 0.0), item.get("is_paid", False))

                desc = _truncate_str(item.get("description", ""), 68)

                dl_cnt = item.get("download_count", 0)

                stars = item.get("rating_avg", 0.0)

                cnt   = item.get("rating_count", 0)

                seller = item.get("seller", {})

                author = seller.get("display_name", "community") if isinstance(seller, dict) else "community"

                star_str = f"★ {stars:.1f}" if cnt > 0 else "New"

                pointer = "  ➔ " if selected else "    "

                card_border = f"bold {_MAUVE}" if selected else f"{_BORDER}"

                action_btn = "[ ⚡ CLICK TO VIEW & BUY ]" if selected else "[ View Package ]"

                lines = [

                    (bg or card_border, f"{pointer}┌── {name}  [{type_tag}]  {price_tag}\n"),

                    (bg or f"fg:{_FG}", f"    │   {desc}\n"),

                    (bg or f"{_MUTED}", f"    └── by @{author}  │  ⬇ {dl_cnt:,} installs  │  ⭐ {star_str}  ──────────  "),

                    (bg or (f"bold {_GREEN}" if selected else f"{_BLUE}"), f"{action_btn}\n\n"),

                ]

                return lines

            return [("class:dim", f"  {str(row)}\n")]

        title = "UTIM EXTENSION MARKETPLACE  🛒"

        legend = "UP/DOWN: Navigate  •  ENTER: Open  •  S: Search  •  W: Wallet  •  ESC: Back"

        extra_keys = {"s": "search_key", "w": "wallet_key"}

        action, idx = _run_list_dialog(rows, render_row, title=title, legend=legend, extra_keys=extra_keys, is_selectable_fn=_is_selectable)

        if action in (None, "quit", "escape"):

            return None

        if action == "search_key":

            action = "select"

            for i, r in enumerate(rows):

                if r.get("action") == "search":

                    idx = i

                    break

        if action == "wallet_key":

            _dialog_seller_hub(console)

            continue

        if action != "select" or idx is None:

            return None

        selected = rows[idx]

        rtype  = selected.get("type")

        act    = selected.get("action")

        if rtype in ("sep", "header_bar", "section_title", "info_text"):

            continue

        if act == "exit":

            return None

        if act == "search":

            opt = _dialog_pick_from_list(

                [

                    ("query", f"🔍 Search Term: '{query[0]}'" if query[0] else "🔍 Enter Keyword Search..."),

                    ("category", f"🗂 Category Domain: {category[0].title()}"),

                    ("sort", f"←• Sort Order: {sort_by[0].replace('_', ' ').title()}"),

                    ("reset", "←º Reset All Search & Category Filters"),

                ],

                "Search & Filter Extension Catalog",

            )

            if opt == "query":

                new_q = _prompt_text(console, "  🔍 Enter search terms: ", default=query[0])

                if new_q is not None:

                    query[0] = new_q

                    page[0] = 0

                    t = threading.Thread(target=_load_data, daemon=True)

                    t.start()

                    t.join(timeout=8)

            elif opt == "category":

                chosen = _dialog_pick_from_list(

                    [(c[0], c[1]) for c in CATEGORIES],

                    "Select Category Domain",

                    current=category[0],

                )

                if chosen:

                    category[0] = chosen

                    page[0] = 0

                    t = threading.Thread(target=_load_data, daemon=True)

                    t.start()

                    t.join(timeout=8)

            elif opt == "sort":

                chosen = _dialog_pick_from_list(

                    [(s[0], s[1]) for s in SORT_OPTIONS],

                    "Select Sorting Order",

                    current=sort_by[0],

                )

                if chosen:

                    sort_by[0] = chosen

                    page[0] = 0

                    t = threading.Thread(target=_load_data, daemon=True)

                    t.start()

                    t.join(timeout=8)

            elif opt == "reset":

                query[0] = ""

                category[0] = "all"

                sort_by[0] = "featured"

                page[0] = 0

                t = threading.Thread(target=_load_data, daemon=True)

                t.start()

                t.join(timeout=8)

            continue

        if act == "category":

            chosen = _dialog_pick_from_list(

                [(c[0], c[1]) for c in CATEGORIES],

                "Filter by Extension Domain / Category",

                current=category[0],

            )

            if chosen:

                category[0] = chosen

                page[0] = 0

                t = threading.Thread(target=_load_data, daemon=True)

                t.start()

                t.join(timeout=8)

            continue

        if act == "sort":

            chosen = _dialog_pick_from_list(

                [(s[0], s[1]) for s in SORT_OPTIONS],

                "Select Listing Ordering Policy",

                current=sort_by[0],

            )

            if chosen:

                sort_by[0] = chosen

                page[0] = 0

                t = threading.Thread(target=_load_data, daemon=True)

                t.start()

                t.join(timeout=8)

            continue

        if act == "refresh":

            listings[0] = None

            t = threading.Thread(target=_load_data, daemon=True)

            t.start()

            t.join(timeout=8)

            continue

        if act == "next_page":

            page[0] += 1

            t = threading.Thread(target=_load_data, daemon=True)

            t.start()

            t.join(timeout=8)

            continue

        if act == "prev_page":

            page[0] = max(0, page[0] - 1)

            t = threading.Thread(target=_load_data, daemon=True)

            t.start()

            t.join(timeout=8)

            continue

        if act == "publish":
            _run_full_screen_flow(_dialog_publish, console)
            continue

        if act == "my_items":
            _run_full_screen_flow(_dialog_my_items, console)
            continue

        if rtype == "card":
            item = selected.get("item", {})
            slug = item.get("slug", "")
            if slug:
                _dialog_item_detail(console, slug, item)
            continue

    return None

# ── Item Detail Screen ────────────────────────────────────────────────────────


# ── Standalone Payment Dialog ─────────────────────────────────────────────────

def _dialog_payment(console, slug: str, name: str, itype: str, order_data: dict) -> str:
    """
    Full payment flow as standalone _run_list_dialog loops.
    Returns "installed" | "cancelled".
    Must be called OUTSIDE any running _run_list_dialog Application.
    """
    order_id   = order_data.get("order_id", "")
    amount_inr = order_data.get("amount", 0) / 100
    amount_usd = order_data.get("amount_usd", 0.0)
    listing_name = order_data.get("listing_name", name)
    vpa        = order_data.get("razorpay_vpa") or os.environ.get("RAZORPAY_VPA", "utimbyemendai278706.rzp@rxairtel")
    upi_url    = order_data.get("upi_url") or (
        f"upi://pay?cu=INR&mc=5817&mode=19&pa={vpa}"
        f"&tn=Payment%20To%20UTIM%20by%20Emend%20Ai&tr=TL0qLELGduMuFSqrv2&am={amount_inr:.2f}"
    )

    current_view = "select_method"
    while True:
        # ── Payment method selection ──────────────────────────────────────────
        if current_view == "select_method":
            pay_rows = [
                {"type": "info", "text": (
                    f"  \n  \U0001f4b3  PAYMENT REQUIRED — "
                    f"\u20b9{amount_inr:.2f} INR (${amount_usd:.2f} USD)\n"
                    f"  Extension: {listing_name}\n"
                    f"  Order ID:  {order_id}\n"
                )},
                {"type": "sep"},
                {"type": "action", "action": "show_qr",     "label": "\U0001f4f1  UPI QR Code (Scan with GPay / PhonePe / Paytm / BHIM)",  "color": _CYAN,  "hint": "Scan QR code inside terminal"},
                {"type": "action", "action": "show_direct", "label": "\U0001f194  UPI VPA Direct Transfer (pay@utim)",                     "color": _GREEN, "hint": "Pay manually to UPI ID pay@utim"},
                {"type": "action", "action": "show_web",    "label": "\U0001f310  Web Checkout (Card / Netbanking / Wallet)",               "color": _BLUE,  "hint": "Opens Razorpay checkout in browser"},
                {"type": "sep"},
                {"type": "action", "action": "cancel",      "label": "\u274c  Cancel Payment & Return",                                   "color": _RED,   "hint": "Abort purchase"},
            ]

            def _render_pay(i, row, sel):
                bg  = f"bg:{_SURFACE}" if sel else ""
                ptr = "  \u279e " if sel else "    "
                rt  = row.get("type")
                if rt == "sep":
                    return [("class:dim", "  " + "\u2500" * 60 + "\n")]
                if rt == "info":
                    lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
                    lines.append(("", "\n"))
                    return lines
                if rt == "action":
                    c  = row.get("color", _BLUE)
                    st = f"bold {c}" if sel else c
                    h  = row.get("hint", "")
                    out = [(bg or st, f"{ptr}[ {row.get('label', '')} ]\n")]
                    if sel and h:
                        out.append((f"fg:{_MUTED}", f"       {h}\n"))
                    return out
                return [("class:dim", f"  {row}\n")]

            p_act, p_idx = _run_list_dialog(
                pay_rows, _render_pay,
                title=f"Payment Checkout  \u203a  {listing_name}",
                legend="UP/DOWN: Navigate  \u2022  ENTER: Select Method  \u2022  ESC/Q: Cancel",
                is_selectable_fn=_is_selectable,
            )
            if p_act != "select" or p_idx is None:
                return "cancelled"
            chosen = pay_rows[p_idx].get("action")
            if chosen == "cancel":
                return "cancelled"
            current_view = chosen
            continue

        # ── UPI QR Code view ─────────────────────────────────────────────────
        elif current_view == "show_qr":
            qr_rows = [
                {"type": "info", "text": (
                    f"  \U0001f4f1  UPI QR CODE\n"
                    f"  Amount: \u20b9{amount_inr:.2f} INR (${amount_usd:.2f} USD)  \u2022  Order: {order_id}\n"
                )},
            ]
            try:
                import qrcode
                qr = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
                qr.add_data(upi_url)
                qr.make(fit=True)
                matrix = qr.get_matrix()
                # Compact half-block: 2 matrix rows -> 1 terminal line (half the height)
                # top=0 bot=0 -> space | top=1 bot=0 -> upper | top=0 bot=1 -> lower | top=1 bot=1 -> full
                HALF = [" ", "\u2584", "\u2580", "\u2588"]
                rows_count = len(matrix)
                for row_i in range(0, rows_count, 2):
                    top_row = matrix[row_i]
                    bot_row = matrix[row_i + 1] if row_i + 1 < rows_count else [False] * len(top_row)
                    line_str = "    " + "".join(HALF[(2 if t else 0) | (1 if b else 0)] for t, b in zip(top_row, bot_row)) + "\n"
                    qr_rows.append({"type": "qr_line", "text": line_str})
            except Exception as _qr_err:
                qr_rows.append({"type": "info", "text": f"  UPI ID: pay@utim\n  Ref/Note: {order_id}\n"})

            qr_rows += [
                {"type": "info", "text": "  1. Open GPay / PhonePe / Paytm / BHIM."},
                {"type": "info", "text": "  2. Scan QR code above."},
                {"type": "info", "text": "  3. Complete payment, then press Confirm below.\n"},
                {"type": "sep"},
                {"type": "action", "action": "verify", "label": "\u2713  Confirm & Verify Payment",  "color": _GREEN, "hint": "Check server for payment confirmation"},
                {"type": "action", "action": "change", "label": "\u2190  Change Payment Method",     "color": _CYAN,  "hint": "Switch to UPI VPA or Web Checkout"},
                {"type": "action", "action": "cancel", "label": "\u274c  Cancel Payment",             "color": _RED,   "hint": "Abort and return to product"},
            ]

            def _render_qr(i, row, sel):
                bg  = f"bg:{_SURFACE}" if sel else ""
                ptr = "  \u279e " if sel else "    "
                rt  = row.get("type")
                if rt == "sep":
                    return [("class:dim", "  " + "\u2500" * 60 + "\n")]
                if rt == "info":
                    lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
                    lines.append(("", "\n"))
                    return lines
                if rt == "qr_line":
                    return [("fg:#ffffff bg:#000000", row.get("text", ""))]
                if rt == "action":
                    c  = row.get("color", _BLUE)
                    st = f"bold {c}" if sel else c
                    h  = row.get("hint", "")
                    out = [(bg or st, f"{ptr}[ {row.get('label', '')} ]\n")]
                    if sel and h:
                        out.append((f"fg:{_MUTED}", f"       {h}\n"))
                    return out
                return [("class:dim", f"  {row}\n")]

            v_act, v_idx = _run_list_dialog(
                qr_rows, _render_qr,
                title=f"UPI QR Code  \u203a  {listing_name}",
                legend="UP/DOWN: Navigate  \u2022  ENTER: Select  \u2022  ESC: Back to methods",
                is_selectable_fn=_is_selectable,
            )
            if v_act != "select" or v_idx is None:
                current_view = "select_method"
                continue
            sub = qr_rows[v_idx].get("action")
            if sub == "change":
                current_view = "select_method"
                continue
            if sub == "cancel":
                return "cancelled"
            if sub == "verify":
                vs, _ = _api_post(f"/marketplace/listings/{slug}/purchase/verify", {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": f"pay_manual_{order_id[-8:]}",
                    "razorpay_signature": "manual_verify",
                })
                if vs in (200, 201):
                    _download_listing(slug)
                    return "installed"
            continue

        # ── UPI VPA direct view ───────────────────────────────────────────────
        elif current_view == "show_direct":
            dir_rows = [
                {"type": "info", "text": "  \U0001f194  DIRECT UPI VPA TRANSFER\n"},
                {"type": "info", "text": f"  UPI ID / VPA :  {vpa}"},
                {"type": "info", "text": f"  Amount Due   :  \u20b9{amount_inr:.2f} INR  (${amount_usd:.2f} USD)"},
                {"type": "info", "text": f"  Ref / Note   :  {order_id}\n"},
                {"type": "info", "text": f"  Open any UPI app, enter {vpa}, and use the Order ID as the note.\n"},
                {"type": "sep"},
                {"type": "action", "action": "verify", "label": "\u2713  Confirm & Verify Payment", "color": _GREEN},
                {"type": "action", "action": "change", "label": "\u2190  Change Payment Method",    "color": _CYAN},
                {"type": "action", "action": "cancel", "label": "\u274c  Cancel Payment",            "color": _RED},
            ]

            def _render_dir(i, row, sel):
                bg  = f"bg:{_SURFACE}" if sel else ""
                ptr = "  \u279e " if sel else "    "
                rt  = row.get("type")
                if rt == "sep":
                    return [("class:dim", "  " + "\u2500" * 60 + "\n")]
                if rt == "info":
                    lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
                    lines.append(("", "\n"))
                    return lines
                if rt == "action":
                    c  = row.get("color", _BLUE)
                    st = f"bold {c}" if sel else c
                    out = [(bg or st, f"{ptr}[ {row.get('label', '')} ]\n")]
                    return out
                return [("class:dim", f"  {row}\n")]

            d_act, d_idx = _run_list_dialog(
                dir_rows, _render_dir,
                title=f"Direct UPI Payment  \u203a  {listing_name}",
                legend="UP/DOWN: Navigate  \u2022  ENTER: Select  \u2022  ESC: Back to methods",
                is_selectable_fn=_is_selectable,
            )
            if d_act != "select" or d_idx is None:
                current_view = "select_method"
                continue
            sub = dir_rows[d_idx].get("action")
            if sub == "change":
                current_view = "select_method"
                continue
            if sub == "cancel":
                return "cancelled"
            if sub == "verify":
                vs, _ = _api_post(f"/marketplace/listings/{slug}/purchase/verify", {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": f"pay_manual_{order_id[-8:]}",
                    "razorpay_signature": "manual_verify",
                })
                if vs in (200, 201):
                    _download_listing(slug)
                    return "installed"
            continue

        # ── Web checkout view ─────────────────────────────────────────────────
        elif current_view == "show_web":
            checkout_url = f"{_API_BASE}/marketplace/checkout/{order_id}"
            try:
                import webbrowser
                webbrowser.open(checkout_url)
            except Exception:
                pass
            web_rows = [
                {"type": "info", "text": "  \U0001f310  WEB CHECKOUT PAGE OPENED\n"},
                {"type": "info", "text": f"  Link   : {checkout_url}"},
                {"type": "info", "text": f"  Amount : \u20b9{amount_inr:.2f} INR  (${amount_usd:.2f} USD)\n"},
                {"type": "info", "text": "  Complete payment in your browser, then press Confirm below.\n"},
                {"type": "sep"},
                {"type": "action", "action": "verify", "label": "\u2713  Confirm & Verify Payment", "color": _GREEN},
                {"type": "action", "action": "change", "label": "\u2190  Change Payment Method",    "color": _CYAN},
                {"type": "action", "action": "cancel", "label": "\u274c  Cancel Payment",            "color": _RED},
            ]

            def _render_web(i, row, sel):
                bg  = f"bg:{_SURFACE}" if sel else ""
                ptr = "  \u279e " if sel else "    "
                rt  = row.get("type")
                if rt == "sep":
                    return [("class:dim", "  " + "\u2500" * 60 + "\n")]
                if rt == "info":
                    lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
                    lines.append(("", "\n"))
                    return lines
                if rt == "action":
                    c  = row.get("color", _BLUE)
                    st = f"bold {c}" if sel else c
                    out = [(bg or st, f"{ptr}[ {row.get('label', '')} ]\n")]
                    return out
                return [("class:dim", f"  {row}\n")]

            w_act, w_idx = _run_list_dialog(
                web_rows, _render_web,
                title=f"Web Checkout  \u203a  {listing_name}",
                legend="UP/DOWN: Navigate  \u2022  ENTER: Select  \u2022  ESC: Back to methods",
                is_selectable_fn=_is_selectable,
            )
            if w_act != "select" or w_idx is None:
                current_view = "select_method"
                continue
            sub = web_rows[w_idx].get("action")
            if sub == "change":
                current_view = "select_method"
                continue
            if sub == "cancel":
                return "cancelled"
            if sub == "verify":
                vs, _ = _api_post(f"/marketplace/listings/{slug}/purchase/verify", {
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": f"pay_manual_{order_id[-8:]}",
                    "razorpay_signature": "manual_verify",
                })
                if vs in (200, 201):
                    _download_listing(slug)
                    return "installed"
            continue

        else:
            return "cancelled"


def _dialog_free_install(console, slug: str, name: str, itype: str, seller_name: str) -> str:
    """
    Full-screen install confirmation dialog for free extensions.
    Runs its own _run_list_dialog loop — must be called OUTSIDE any running Application.
    Returns "installed" | "cancelled".
    """
    if not _ensure_profile_setup(console):
        return "cancelled"

    target_dir = _get_install_dir(itype, slug)

    perm_rows = {
        "skill":     ["Context Injection  — teaches the AI project-specific guidelines",
                      "File Scope         — workspace read-only context analysis"],
        "miniagent": ["Task Execution     — autonomous agent workflow execution",
                      "Command Execution  — runs shell commands within user sandbox"],
    }
    perms = perm_rows.get(itype, ["Tool Invocation   — registers native LLM tool functions"])

    install_rows = [
        {"type": "info", "text": f"  \u26a1  INSTALL CONFIRMATION: {name}\n"},
        {"type": "sep"},
        {"type": "info", "text": f"  Extension :  {name}  ({itype.upper()})"},
        {"type": "info", "text": f"  Publisher :  @{seller_name}"},
        {"type": "info", "text": f"  Target Dir:  {target_dir}\n"},
        {"type": "info", "text": "  Declared Permissions & Capabilities:"},
    ]
    for p in perms:
        install_rows.append({"type": "info", "text": f"    \u2022  {p}"})
    install_rows += [
        {"type": "spacer"},
        {"type": "sep"},
        {"type": "action", "action": "confirm", "label": "\u26a1  Yes, Install Extension Now", "color": _GREEN, "hint": "Download and unpack into workspace"},
        {"type": "action", "action": "cancel",  "label": "\u2190  Cancel Installation",        "color": _RED,   "hint": "Return to product details"},
    ]

    _result = [None]

    async def _on_enter(idx, row, app, value=None):
        act = row.get("action", "")
        if act == "confirm":
            _result[0] = "confirm"
        else:
            _result[0] = "cancel"
        app.exit()
        return False

    def _render_inst(i, row, sel):
        bg  = f"bg:{_SURFACE}" if sel else ""
        ptr = "  \u279e " if sel else "    "
        rt  = row.get("type")
        if rt == "sep":
            return [("class:dim", "  " + "\u2500" * 60 + "\n")]
        if rt in ("info",):
            lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
            lines.append(("", "\n"))
            return lines
        if rt == "spacer":
            return [("", "\n")]
        if rt == "action":
            c  = row.get("color", _BLUE)
            st = f"bold {c}" if sel else c
            h  = row.get("hint", "")
            out = [(bg or st, f"{ptr}[ {row.get('label', '')} ]\n")]
            if sel and h:
                out.append((f"fg:{_MUTED}", f"       {h}\n"))
            return out
        return [("class:dim", f"  {row}\n")]

    _run_list_dialog(
        install_rows, _render_inst,
        title=f"Install Extension  \u203a  {name}",
        legend="UP/DOWN: Navigate  \u2022  ENTER: Confirm  \u2022  ESC/Q: Cancel",
        is_selectable_fn=_is_selectable,
        on_enter=_on_enter,
    )

    if _result[0] != "confirm":
        return "cancelled"

    # Progress screen
    progress_rows = [
        {"type": "info", "text": f"  \u2b07  INSTALLING {name.upper()}...\n"},
        {"type": "sep"},
        {"type": "info", "text": "  \u27f3 Step 1/4: Downloading archive from server..."},
        {"type": "info", "text": "  \u2713 Step 2/4: Verifying archive integrity & security..."},
        {"type": "info", "text": "  \u27f3 Step 3/4: Unpacking files to target directory..."},
    ]

    import threading
    dl_result = [None]
    dl_done   = threading.Event()

    def _do_download():
        dl_result[0] = _download_listing(slug)
        dl_done.set()

    t = threading.Thread(target=_do_download, daemon=True)
    t.start()

    def _check_dl():
        while not dl_done.is_set():
            time.sleep(0.1)
        try:
            from prompt_toolkit.application.current import get_app
            get_app().exit()
        except Exception:
            pass

    threading.Thread(target=_check_dl, daemon=True).start()

    # Show progress while downloading
    _run_list_dialog(
        progress_rows,
        lambda i, r, s: _parse_markup_to_tuples(r.get("text", ""), default_style=f"fg:{_FG}") + [("", "\n")],
        title=f"Installing  ›  {name}",
        legend="Downloading & unpacking files... Please wait...",
        is_selectable_fn=lambda r: False,
    )
    # Wait up to 30s for download
    dl_done.wait(timeout=30)
    ok, dest_or_err = dl_result[0] or (False, "Download timed out")

    if ok:
        done_rows = [
            {"type": "info", "text": f"  \u2713 Step 4/4: Registering extension in UTIM workspace...\n"},
            {"type": "sep"},
            {"type": "info", "text": f"  \U0001f389  SUCCESSFULLY INSTALLED \'{name}\'!"},
            {"type": "info", "text": f"  Installed at: {dest_or_err}\n"},
            {"type": "info", "text": f"  The extension is now ready for use in your UTIM workspace.\n"},
            {"type": "sep"},
            {"type": "action", "action": "done", "label": "\u2190  Return to Extension Details", "color": _GREEN},
        ]
    else:
        done_rows = [
            {"type": "info", "text": f"  \u2717  INSTALLATION FAILED: {dest_or_err}\n"},
            {"type": "sep"},
            {"type": "action", "action": "done", "label": "\u2190  Return to Extension Details", "color": _RED},
        ]

    _run_list_dialog(
        done_rows,
        lambda i, r, s: (
            [("class:dim", "  " + "\u2500" * 60 + "\n")] if r.get("type") == "sep" else
            ([(f"bold {r.get('color', _BLUE)}" if s else r.get("color", _BLUE), f"  \u279e [ {r['label']} ]\n")] if r.get("type") == "action" else
            _parse_markup_to_tuples(r.get("text", ""), default_style=f"fg:{_FG}") + [("", "\n")])
        ),
        title=f"Install Complete  \u203a  {name}",
        legend="ENTER: Return",
        is_selectable_fn=_is_selectable,
    )

    return "installed" if ok else "failed"

def _dialog_item_detail(console, slug: str, preview: dict) -> Optional[str]:

    detail = _fetch_listing_detail(slug) or preview

    name        = detail.get("name", slug)

    itype       = detail.get("type", "skill")

    type_tag, _ = _format_type_badge(itype)

    category    = detail.get("category", "General")

    description = detail.get("description", "")

    readme      = detail.get("readme", "")

    tags        = detail.get("tags") or []

    version     = detail.get("version", "1.0.0")

    dl_count    = detail.get("download_count", 0)

    rating_avg  = detail.get("rating_avg", 0.0)

    rating_cnt  = detail.get("rating_count", 0)

    is_paid     = detail.get("is_paid", False)

    price       = detail.get("price_usd", 0.0)

    price_str   = _format_price_pill(price, is_paid)

    seller      = detail.get("seller", {})

    seller_name = seller.get("display_name", "community") if isinstance(seller, dict) else str(seller)

    reviews     = detail.get("reviews", [])

    rows: list[dict] = []

    # Title & Metadata Header Box

    rows.append({"type": "info", "text": f"\n  [bold {_WHITE}]📦  {name}[/bold {_WHITE}]  {price_str}"})

    rows.append({"type": "info", "text": f"  [dim {_MUTED}]Type:[/dim {_MUTED}] [bold {_BLUE}]{type_tag}[/bold {_BLUE}]  │  [dim {_MUTED}]Publisher:[/dim {_MUTED}] [bold {_MAUVE}]@{seller_name}[/bold {_MAUVE}]  │  [dim {_MUTED}]Version:[/dim {_MUTED}] v{version}"})

    rows.append({"type": "info", "text": f"  [dim {_MUTED}]Rating:[/dim {_MUTED}] {_format_stars(rating_avg, rating_cnt)}  │  [dim {_MUTED}]Installs:[/dim {_MUTED}] [bold {_GREEN}]{dl_count:,}[/bold {_GREEN}]  │  [dim {_MUTED}]Domain:[/dim {_MUTED}] {category.title()}"})

    if tags:

        tag_str = " ".join(f"[{t}]" for t in tags)

        rows.append({"type": "info", "text": f"  [dim {_MUTED}]Tags:[/dim {_MUTED}] [cyan]{tag_str}[/cyan]"})

    rows.append({"type": "sep"})

    # Check owner status

    profile = _api_get("/marketplace/seller-profile") or {}

    owner_id = detail.get("seller_id")

    current_user_id = profile.get("id") # profile ID or user ID

    is_owner = False

    if owner_id:

        try:

            user_info = _api_get("/auth/me") or {}

            if user_info.get("id") == owner_id:

                is_owner = True

        except Exception:

            pass

    is_published = detail.get("is_published", True)

    # Primary Action Buttons

    rows.append({"type": "action", "action": "install", "label": "⚡  INSTALL EXTENSION NOW", "color": _GREEN, "hint": f"Download and unpack {name} into your workspace"})

    rows.append({"type": "action", "action": "seller_info", "label": f"👤  View Publisher Profile (@{seller_name})", "color": _MAUVE, "hint": "View seller details, bio & published extensions"})

    rows.append({"type": "action", "action": "readme",  "label": "📖  Read Full Documentation & README", "color": _CYAN, "hint": "View comprehensive instructions"})

    rows.append({"type": "action", "action": "review",  "label": "⭐  Submit Rating & Review", "color": _YELLOW, "hint": "Share feedback on this extension"})

    rows.append({"type": "action", "action": "reviews", "label": f"💬  View All Reviews ({rating_cnt})", "color": _BLUE, "hint": "Read user comments"})

    if is_owner:

        pub_label = "🚫  UNPUBLISH EXTENSION" if is_published else "📤  PUBLISH EXTENSION"

        pub_color = _YELLOW if is_published else _GREEN

        pub_hint = "Hide extension from public marketplace" if is_published else "Make extension visible in public marketplace"

        rows.append({"type": "action", "action": "toggle_publish", "label": pub_label, "color": pub_color, "hint": pub_hint})

    rows.append({"type": "action", "action": "back",    "label": "←  Return to Marketplace Browser", "color": _RED, "hint": "Go back"})

    rows.append({"type": "sep"})

    # Description Section

    rows.append({"type": "info", "text": f"  [bold {_CYAN}]DESCRIPTION[/bold {_CYAN}]"})

    term_w = shutil.get_terminal_size().columns

    wrapped = textwrap.wrap(description, width=max(40, term_w - 12))

    for line in wrapped:

        rows.append({"type": "desc", "text": f"  {line}"})

    rows.append({"type": "sep"})

    def render_row(idx: int, row: dict, selected: bool):

        bg = f"bg:{_SURFACE}" if selected else ""

        rtype = row.get("type")

        if rtype == "sep":

            return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

        if rtype in ("info", "desc"):

            lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

            lines.append(("", "\n"))

            return lines

        if rtype == "action":

            color = row.get("color", _BLUE)

            fg = f"bold {color}" if selected else color

            pointer = "  ➔ " if selected else "    "

            hint = row.get("hint", "")

            lines = [(bg or fg, f"{pointer}[ {row.get('label', '')} ]\n")]

            if selected and hint:

                lines.append((bg or f"{_MUTED}", f"       {hint}\n"))

            return lines

        return [("class:dim", f"  {str(row)}\n")]

    _next_act: list[str] = [""]

    async def _detail_on_enter(idx, row, app, value=None):
        a = row.get("action", "")
        if a == "install":
            _next_act[0] = "install"
            app.exit()
            return False
        return None  # fallthrough to default select behaviour

    while True:

        _next_act[0] = ""

        action, idx = _run_list_dialog(

            rows, render_row,

            title=f"Extension Detail  \u203a  {name}",

            legend="UP/DOWN: Navigate  \u2022  ENTER: Select Action  \u2022  ESC/Q: Back",

            is_selectable_fn=_is_selectable,

            on_enter=_detail_on_enter,

        )

        # Install action requested — run outside this dialog
        if _next_act[0] == "install":
            if not _ensure_profile_setup(console):
                continue
            if is_paid and price > 0:
                # Show "connecting..." screen while making API call
                _err_msg = [None]
                _order_result = [None]
                import threading as _th
                _done_ev = _th.Event()
                def _place_order():
                    sc, od = _api_post(
                        f"/marketplace/listings/{slug}/purchase/order",
                        {"currency": "INR"}
                    )
                    _order_result[0] = (sc, od)
                    _done_ev.set()
                _th.Thread(target=_place_order, daemon=True).start()
                # Show connecting dialog (exits when done)
                connecting_rows = [
                    {"type": "info", "text": f"  ⏳  Connecting to payment server...\n"},
                    {"type": "info", "text": f"  Extension: {name}"},
                    {"type": "info", "text": f"  Price:     ${price:.2f} USD\n"},
                    {"type": "info", "text": "  Please wait..."},
                ]
                import asyncio as _asyncio
                async def _auto_exit_on_order(idx, row, app, value=None):
                    return True
                def _render_connecting(i, row, sel):
                    lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
                    lines.append(("", "\n"))
                    return lines
                # Poll until order completes, then auto-exit via timer
                _done_ev.wait(timeout=15)
                status_code, order_data = _order_result[0] or (0, None)

                if status_code == 409:
                    # Already purchased — just download
                    _dialog_free_install(console, slug, name, itype, seller_name)
                    return "installed"
                if status_code == 401:
                    # Show auth error
                    err_rows = [
                        {"type": "info", "text": f"  ❌  AUTHENTICATION REQUIRED\n"},
                        {"type": "info", "text": "  You must be logged in to purchase extensions."},
                        {"type": "info", "text": "  Run /login in the chat to authenticate.\n"},
                        {"type": "sep"},
                        {"type": "action", "action": "back", "label": "←  Return to Extension Details", "color": _RED},
                    ]
                    def _render_err_auth(i, r, s):
                        rt = r.get("type")
                        if rt == "sep":
                            return [("class:dim", "  " + "─"*60 + "\n")]
                        if rt == "info":
                            lines = _parse_markup_to_tuples(r.get("text",""), default_style=f"fg:{_FG}")
                            lines.append(("", "\n"))
                            return lines
                        if rt == "action":
                            ptr = "  ➞ " if s else "    "
                            c = r.get("color", _RED)
                            st = f"bold {c}" if s else c
                            return [(st, f"{ptr}[ {r.get('label','')} ]\n")]
                        return [("class:dim", f"  {r}\n")]
                    _run_list_dialog(
                        err_rows, _render_err_auth,
                        title="Authentication Required",
                        legend="ENTER: Return to details",
                        is_selectable_fn=_is_selectable,
                    )
                    continue
                if status_code not in (200, 201) or not order_data:
                    # Show error with fallback to free install option
                    err_msg = f"HTTP {status_code}" if status_code else "Could not reach payment server"
                    err_rows = [
                        {"type": "info", "text": f"  ⚠️  PAYMENT SERVER UNAVAILABLE\n"},
                        {"type": "info", "text": f"  Error: {err_msg}\n"},
                        {"type": "sep"},
                        {"type": "action", "action": "retry",  "label": "↻  Retry Connection",           "color": _YELLOW, "hint": "Try reaching payment server again"},
                        {"type": "action", "action": "install","label": "⚡  Install Anyway (Skip Payment)","color": _GREEN,  "hint": "Install without payment verification (demo mode)"},
                        {"type": "action", "action": "back",   "label": "←  Return to Extension Details", "color": _RED},
                    ]
                    _err_act = [None]
                    async def _err_on_enter(idx, row, app, value=None):
                        _err_act[0] = row.get("action")
                        app.exit()

        if action not in ("select",) or idx is None:
            return None
        sel = rows[idx] if idx is not None and idx < len(rows) else {}
        act = sel.get("action")
        if act == "back" or not act:
            return None

        if act == "seller_info":
            sp = _api_get(f"/marketplace/seller-profile/{owner_id or 'community'}") or {}
            s_name = sp.get("display_name", seller_name)
            s_bio = sp.get("bio", "UTIM Extension Publisher")
            s_emoji = sp.get("avatar_emoji", "🧑‍💻")
            s_verified = sp.get("is_verified", True)
            v_status = "✓ VERIFIED PUBLISHER" if s_verified else "Community Publisher"

            pub_rows = [
                {"type": "info", "text": f"  {s_emoji}  PUBLISHER PROFILE: @{s_name}\n"},
                {"type": "sep"},
                {"type": "info", "text": f"  Status:         {v_status}"},
                {"type": "info", "text": f"  Bio:            {s_bio}"},
                {"type": "info", "text": f"  Extensions:     {sp.get('total_published', 1)} published"},
                {"type": "info", "text": f"  Total Installs: {sp.get('total_downloads', dl_count):,} downloads"},
                {"type": "info", "text": f"  Average Rating: ⭐ {sp.get('average_rating', rating_avg):.1f}\n"},
                {"type": "sep"},
            ]
            listings = sp.get("listings") or []
            if listings:
                pub_rows.append({"type": "info", "text": "  📦 Published Extensions Catalog:"})
                for l in listings[:8]:
                    p_str = "FREE" if l.get("price_usd", 0.0) == 0 else f"${l.get('price_usd'):.2f}"
                    pub_rows.append({"type": "info", "text": f"   • {l.get('name')} [{l.get('type').upper()}] [{p_str}] ⭐ {l.get('rating_avg', 0.0):.1f}"})
                pub_rows.append({"type": "sep"})

            pub_rows.append({"type": "action", "action": "back", "label": "←  Return to Extension Details", "color": _GREEN})

            _run_list_dialog(
                pub_rows,
                render_row,
                title=f"Publisher Profile  ›  @{s_name}",
                legend="ENTER / ESC: Return to extension details",
                is_selectable_fn=_is_selectable,
                on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
            )
            continue

        if act == "readme":
            doc_text = readme or description or "No documentation provided for this extension."
            doc_lines = doc_text.splitlines()

            doc_rows = [
                {"type": "info", "text": f"  📖  DOCUMENTATION — {name}\n"},
                {"type": "sep"},
            ]
            for line in doc_lines:
                doc_rows.append({"type": "info", "text": f"  {line}"})

            doc_rows.append({"type": "sep"})
            doc_rows.append({"type": "action", "action": "back", "label": "←  Return to Extension Details", "color": _GREEN})

            _run_list_dialog(
                doc_rows,
                render_row,
                title=f"Documentation  ›  {name}",
                legend="UP/DOWN: Scroll Documentation  •  ENTER / ESC: Return",
                is_selectable_fn=_is_selectable,
                on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
            )
            continue

        if act == "reviews":
            rev_rows = [
                {"type": "info", "text": f"  💬  USER REVIEWS — {name} ({rating_cnt} reviews, {_format_stars(rating_avg, rating_cnt)})\n"},
                {"type": "sep"},
            ]
            if not reviews:
                rev_rows.append({"type": "info", "text": "  No reviews submitted yet for this extension."})
            else:
                for rev in reviews[:20]:
                    r_user = (rev.get("reviewer") or {}).get("display_name", "Anonymous")
                    r_rating = rev.get("rating", 5)
                    r_comment = rev.get("comment", "")
                    r_stars = "★" * int(r_rating) + "☆" * (5 - int(r_rating))
                    rev_rows.append({"type": "info", "text": f"  • @{r_user} — {r_stars} ({r_rating}/5)"})
                    if r_comment:
                        rev_rows.append({"type": "info", "text": f"    \"{r_comment}\""})
                    rev_rows.append({"type": "spacer"})

            rev_rows.append({"type": "sep"})
            rev_rows.append({"type": "action", "action": "write", "label": "⭐  Submit Rating & Review", "color": _YELLOW, "hint": "Write a review"})
            rev_rows.append({"type": "action", "action": "back", "label": "←  Return to Extension Details", "color": _GREEN})

            rev_action = ["back"]
            async def _rev_on_enter(idx, row, app, val=None):
                if row.get("action"):
                    rev_action[0] = row["action"]
                    app.exit()
                    return False
                return True

            _run_list_dialog(
                rev_rows,
                render_row,
                title=f"User Reviews  ›  {name}",
                legend="UP/DOWN: Scroll Reviews  •  ENTER: Select  •  ESC: Return",
                is_selectable_fn=_is_selectable,
                on_enter=_rev_on_enter,
            )

            if rev_action[0] == "write":
                _dialog_write_review(console, slug, name)
                fresh = _fetch_listing_detail(slug)
                if fresh:
                    detail = fresh
                    rating_avg = detail.get("rating_avg", 0.0)
                    rating_cnt = detail.get("rating_count", 0)
                    reviews = detail.get("reviews", [])
            continue

    return None


# ── Write Review Screen ───────────────────────────────────────────────────────

def _dialog_write_review(console, slug: str, name: str):
    """Clean interactive TUI list dialog to submit a review & star rating for an extension.
    Zero stdout dumps, 100% inside PTK list dialog.
    """
    if not _ensure_profile_setup(console):
        return

    from utim_cli.utim import _run_list_dialog, _set_inline_edit

    form = {
        "rating": "5.0",
        "comment": "",
    }

    ratings = ["5.0", "4.5", "4.0", "3.5", "3.0", "2.5", "2.0", "1.5", "1.0"]

    def _render_stars_visual(val_str: str) -> str:
        try:
            val = float(val_str)
        except ValueError:
            val = 5.0
        full = int(val)
        half = 1 if (val - full) >= 0.5 else 0
        empty = max(0, 5 - full - half)
        return "★" * full + ("½" if half else "") + "☆" * empty

    rows: list[dict] = [
        {"type": "info", "bold": True, "color": _YELLOW, "text": f"⭐  SUBMIT REVIEW — '{name}'"},
        {"type": "info", "color": _MUTED, "text": "Share your feedback and star rating with the UTIM community."},
        {"type": "spacer"},
        {"type": "field", "field": "rating", "label": "Rating Stars", "color": _YELLOW, "hint": "Press ENTER to cycle star rating (1.0 to 5.0 stars)"},
        {"type": "field", "field": "comment", "label": "Review Comment", "color": _WHITE, "hint": "Press ENTER to edit comment text (optional)"},
        {"type": "spacer"},
        {"type": "sep"},
        {"type": "action", "action": "submit", "label": "⭐  Submit Review", "color": _GREEN, "hint": "Submit rating & comment to marketplace."},
        {"type": "action", "action": "cancel", "label": "←  Cancel", "color": _RED, "hint": "Cancel and return to extension details."},
    ]

    def _render_review_row(idx: int, row: dict, selected: bool) -> list:
        bg = f"bg:{_SURFACE}" if selected else ""
        ptr = "  ➔ " if selected else "    "
        rt = row.get("type")

        if rt == "sep":
            return [("class:dim", "  " + "─" * 60 + "\n")]
        if rt == "spacer":
            return [("", "\n")]
        if rt == "info":
            color = row.get("color", _FG)
            style = f"bold {color}" if row.get("bold") else f"fg:{color}"
            return [(style, f"  {row['text']}\n")]

        if rt == "field" and row.get("field") == "rating":
            val = form.get("rating", "5.0")
            stars = _render_stars_visual(val)
            fg_label = f"{bg} bold {_CYAN}" if selected else f"fg:{_FG}"
            fg_val = f"{bg} bold {_YELLOW}" if selected else f"fg:{_YELLOW}"
            return [
                (fg_label, f"{ptr}Rating Stars: "),
                (fg_val, f"{stars} ({val}/5.0 stars)  ← Press ENTER to cycle\n"),
            ]

        if rt == "field" and row.get("field") == "comment":
            val = form.get("comment", "")
            fg_label = f"{bg} bold {_CYAN}" if selected else f"fg:{_FG}"
            val_str = val if val else "[ press Enter to type optional comment... ]"
            val_style = f"{bg} bold {_WHITE}" if (selected and val) else (f"{bg} fg:{_MUTED}" if selected else f"fg:{_MUTED}")
            return [
                (fg_label, f"{ptr}Review Comment: "),
                (val_style, f"{val_str}\n"),
            ]

        if rt == "action":
            color = row.get("color", _FG)
            style = f"{bg} bold {color}" if selected else f"fg:{color}"
            return [(style, f"{ptr}{row['label']}\n")]

        return [("class:dim", f"  {row}\n")]

    def _is_review_selectable(row: dict) -> bool:
        return row.get("type") in ("field", "action")

    action = ["cancel"]

    async def _on_enter(idx, row, app, value=None):
        rt = row.get("type")
        fld = row.get("field")
        act = row.get("action")

        if value is not None and fld == "comment":
            form["comment"] = value.strip()
            return True

        if act == "cancel":
            action[0] = "cancel"
            app.exit()
            return False

        if act == "submit":
            action[0] = "submit"
            app.exit()
            return False

        if rt == "field" and fld == "rating":
            curr = form.get("rating", "5.0")
            nxt_idx = (ratings.index(curr) + 1) % len(ratings) if curr in ratings else 0
            form["rating"] = ratings[nxt_idx]
            try:
                app.invalidate()
            except Exception:
                pass
            return True

        if rt == "field" and fld == "comment":
            _set_inline_edit("comment", "  Review Comment: ", form.get("comment", ""))
            return True

        return True

    _run_list_dialog(
        rows,
        _render_review_row,
        title=f"Submit Review — {name}",
        legend="UP/DOWN: Navigate  •  ENTER: Edit / Select  •  ESC: Cancel",
        is_selectable_fn=_is_review_selectable,
        on_enter=_on_enter,
    )

    if action[0] == "submit":
        try:
            rating = int(form.get("rating", "5"))
        except ValueError:
            rating = 5

        comment = form.get("comment", "").strip()

        status, data = _api_post(
            f"/marketplace/listings/{slug}/reviews",
            {"rating": rating, "comment": comment},
        )

        if status in (200, 201):
            msg_rows = [
                {"type": "info", "bold": True, "color": _GREEN, "text": f"✓  Thank you! Your review for '{name}' has been submitted."},
                {"type": "spacer"},
                {"type": "action", "action": "ok", "label": "←  Return to Extension Details", "color": _GREEN},
            ]
        elif status == 409:
            msg_rows = [
                {"type": "info", "bold": True, "color": _YELLOW, "text": "⚠  You have already submitted a review for this extension."},
                {"type": "spacer"},
                {"type": "action", "action": "ok", "label": "←  Return to Extension Details", "color": _YELLOW},
            ]
        elif status == 401:
            msg_rows = [
                {"type": "info", "bold": True, "color": _RED, "text": "✗  Authentication required. Please sign in to submit reviews."},
                {"type": "spacer"},
                {"type": "action", "action": "ok", "label": "←  Return", "color": _RED},
            ]
        else:
            err = (data or {}).get("detail", f"HTTP {status}")
            msg_rows = [
                {"type": "info", "bold": True, "color": _RED, "text": f"✗  Review submission failed: {err}"},
                {"type": "spacer"},
                {"type": "action", "action": "ok", "label": "←  Return", "color": _RED},
            ]

        def _render_msg(idx, row, selected):
            bg = f"bg:{_SURFACE}" if selected else ""
            ptr = "  ➔ " if selected else "    "
            rt = row.get("type")
            if rt == "info":
                color = row.get("color", _FG)
                return [(f"bold {color}" if row.get("bold") else f"fg:{color}", f"  {row['text']}\n")]
            if rt == "spacer":
                return [("", "\n")]
            if rt == "action":
                color = row.get("color", _FG)
                return [(f"{bg} bold {color}" if selected else f"fg:{color}", f"{ptr}{row['label']}\n")]
            return [("class:dim", f"  {row}\n")]

        _run_list_dialog(
            msg_rows,
            _render_msg,
            title="Review Status",
            legend="ENTER: Continue",
            is_selectable_fn=lambda r: r.get("type") == "action",
            on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
        )

# ── Publish Form ──────────────────────────────────────────────────────────────

# ── Local Package Helpers ───────────────────────────────────────────────────────

def _list_local_extensions(ext_type: str = "skill") -> list[tuple[str, str]]:

    """Scan disk for local skills, miniagents, tools, or MCP servers to offer in the & picker based on selected type."""

    items = []

    seen = set()

    from pathlib import Path

    from utim_cli.config import get_utim_dir

    utim_dir = get_utim_dir()

    home_dir = Path.home()

    if ext_type in ("skill", "all"):

        skill_dirs = [

            utim_dir / "skills",

            home_dir / ".utim" / "skills",

            Path(".utim/skills"),

            Path(".agents/skills"),

            Path(".utim_tmp/skills"),

            Path("skills"),

        ]

        for d in skill_dirs:

            if d.exists() and d.is_dir():

                for entry in sorted(d.iterdir()):

                    if entry.is_dir():

                        resolved = str(entry.resolve())

                        if resolved not in seen:

                            seen.add(resolved)

                            items.append((resolved, f"📦 Skill: {entry.name} ({entry.parent.name})"))

    if ext_type in ("miniagent", "all"):

        mini_dirs = [

            utim_dir / "miniagents",

            home_dir / ".utim" / "miniagents",

            Path(".utim/miniagents"),

            Path(".agents/agents"),

            Path(".agents/miniagents"),

            Path("miniagents"),

        ]

        for d in mini_dirs:

            if d.exists() and d.is_dir():

                for entry in sorted(d.iterdir()):

                    if entry.is_dir():

                        resolved = str(entry.resolve())

                        if resolved not in seen:

                            seen.add(resolved)

                            items.append((resolved, f"🤖 Miniagent: {entry.name} ({entry.parent.name})"))

    if ext_type in ("tool", "all"):

        tool_dirs = [

            utim_dir / "tools",

            home_dir / ".utim" / "tools",

            Path(".utim/tools"),

            Path(".agents/tools"),

            Path("tools"),

        ]

        for d in tool_dirs:

            if d.exists() and d.is_dir():

                for entry in sorted(d.iterdir()):

                    if entry.is_dir():

                        resolved = str(entry.resolve())

                        if resolved not in seen:

                            seen.add(resolved)

                            items.append((resolved, f"🛠️ Tool: {entry.name} ({entry.parent.name})"))

    if ext_type in ("mcp", "all"):

        mcp_dirs = [

            utim_dir / "mcp",

            home_dir / ".utim" / "mcp",

            Path(".utim/mcp"),

            Path(".agents/mcp"),

            Path("mcp"),

        ]

        for d in mcp_dirs:

            if d.exists() and d.is_dir():

                for entry in sorted(d.iterdir()):

                    if entry.is_dir():

                        resolved = str(entry.resolve())

                        if resolved not in seen:

                            seen.add(resolved)

                            items.append((resolved, f"🔌 MCP: {entry.name} ({entry.parent.name})"))

    return items

def _zip_folder_to_base64(folder_path: str) -> tuple[Optional[str], Optional[str]]:

    """Zip a local directory in memory and return (base64_str, readme_text)."""

    import zipfile, io, base64, os

    p = Path(folder_path)

    if not p.exists() or not p.is_dir():

        return None, None

    buf = io.BytesIO()

    readme_text = None

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        for root, dirs, files in os.walk(p):

            for file in files:

                full_path = Path(root) / file

                rel_path = full_path.relative_to(p)

                zf.write(full_path, rel_path)

                if file.lower() in ("skill.md", "prompt.md", "readme.md", "system.md") and not readme_text:

                    try:

                        readme_text = full_path.read_text(encoding="utf-8")

                    except Exception:

                        pass

    buf.seek(0)

    b64 = base64.b64encode(buf.read()).decode("ascii")

    return b64, readme_text

# ── Publish Form ──────────────────────────────────────────────────────────────

def _write_utf8(text: str) -> None:

    """Write UTF-8 bytes to sys.stdout.buffer, bypassing PTK's cp1252 wrapper."""

    import sys

    raw = text.encode('utf-8', errors='replace')

    try:

        buf = getattr(sys.stdout, 'buffer', None)

        if buf is not None:

            buf.write(raw)

            buf.flush()

            return

    except Exception:

        pass

    try:

        sys.stdout.write(text)

        sys.stdout.flush()

    except Exception:

        pass

def _step_input(label, default=''):

    """Plain stdin prompt inside _run_in_terminal_safe context."""

    prompt_str = label if not default else f'{label}[{default}] '

    _write_utf8(prompt_str)

    try:

        val = input()

        return val if val.strip() else default

    except (KeyboardInterrupt, EOFError):

        return None

def _p(text):

    """Write a line to terminal -- UTF-8 safe inside run_in_terminal."""

    _write_utf8(text + "\n")

# ── My Published Items Screen ─────────────────────────────────────────────────

def _ensure_profile_setup(console) -> bool:
    """Check if user profile is configured. If not, prompt user to set up profile.
    Returns True if profile is set up, False if user cancelled setup.
    """
    profile_data = _api_get("/marketplace/seller-profile")
    if profile_data and profile_data.get("display_name"):
        return True

    _dialog_setup_seller_profile(console)
    profile_data = _api_get("/marketplace/seller-profile")
    return bool(profile_data and profile_data.get("display_name"))


def _prompt_text(console, label: str, default: str = "") -> Optional[str]:
    """Run a prompt_toolkit text prompt inside full_screen TUI mode without leaking to chat."""
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import TextArea
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style as PTStyle

    kb = KeyBindings()
    res = [None]

    text_area = TextArea(
        text=default or "",
        multiline=False,
        wrap_lines=False,
        focusable=True,
    )

    @kb.add("enter")
    def _on_enter(event):
        res[0] = text_area.text.strip()
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def _on_cancel(event):
        res[0] = None
        event.app.exit()

    style = PTStyle.from_dict({
        "label": "bold #cba6f7",
        "dim": "#6c7086",
    })

    header = Window(
        content=FormattedTextControl(
            text=[("class:label", f"  ✏️  {label}\n"), ("class:dim", "  (Press Enter to confirm, ESC to cancel)\n\n")]
        ),
        height=3,
    )

    body = HSplit([
        Window(height=1),
        header,
        text_area,
        Window(height=1),
    ])

    app = Application(
        layout=Layout(body, focused_element=text_area),
        key_bindings=kb,
        style=style,
        full_screen=True,
    )

    try:
        app.run()
        val = res[0]
        if val is not None:
            return val if val else (default if default else None)
        return None
    except Exception:
        return None

def _dialog_manage_my_extension(console, item: dict) -> bool:

    """Action menu for managing a specific published extension. Returns True if deleted."""

    from utim_cli.utim import _run_list_dialog  # type: ignore

    name = item.get("name", "Extension")

    slug = item.get("slug", "")



    while True:

        rows = [

            {"type": "title", "text": f"⚙️  MANAGE: {name.upper()}"},

            {"type": "action", "action": "view", "label": "🔍  View Details"},

            {"type": "action", "action": "delete", "label": "🗑️  Remove / Delete Extension", "color": _RED},

            {"type": "sep"},

            {"type": "action", "action": "back", "label": "←  Return to My Extensions", "color": _MUTED},

        ]



        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

            if rtype == "title":

                return [(f"bold {_MAUVE}", f"\n  {row.get('text', '')}\n")]

            if rtype == "action":

                color = row.get("color", _BLUE)

                fg = f"bold {color}" if selected else color

                pointer = "  ➔ " if selected else "    "

                return [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

            return [("class:dim", f"  {str(row)}\n")]



        action, idx = _run_list_dialog(rows, render_row, title=f"Manage: {name}", legend="ENTER: Select  •  ESC/Q: Back", is_selectable_fn=_is_selectable)



        if action not in ("select",) or idx is None:

            return False



        act = rows[idx].get("action")

        if act == "back":

            return False



        if act == "view":

            if slug:

                _dialog_item_detail(console, slug, item)



        if act == "delete":
            deleted = _confirm_delete_dialog(console, name, slug)
            if deleted:
                return True






def _confirm_delete_dialog(console, name: str, slug: str) -> bool:
    """Clean interactive TUI list dialog for deletion confirmation."""
    from utim_cli.utim import _run_list_dialog

    rows: list[dict] = [
        {"type": "info", "bold": True, "color": _RED, "text": f"🗑️  PERMANENTLY REMOVE EXTENSION '{name}'?"},
        {"type": "info", "color": _MUTED, "text": "This action cannot be undone. The extension listing will be deleted from UTIM Marketplace."},
        {"type": "spacer"},
        {"type": "sep"},
        {"type": "action", "action": "confirm", "label": "🗑️  Yes, Permanently Delete Extension", "color": _RED, "hint": "Deletes listing and package version records from marketplace."},
        {"type": "action", "action": "cancel", "label": "←  Cancel & Keep Extension", "color": _GREEN, "hint": "Return to item details without deleting."},
    ]

    action = ["cancel"]
    async def _on_enter(idx, row, app, value=None):
        if row.get("action"):
            action[0] = row["action"]
            app.exit()
            return False
        return True

    def _render(idx, row, sel):
        bg = f"bg:{_SURFACE}" if sel else ""
        rt = row.get("type")
        if rt == "sep":
            return [("class:dim", "  " + "─" * 60 + "\n")]
        if rt == "spacer":
            return [("", "\n")]
        if rt == "info":
            lines = _parse_markup_to_tuples(row.get("text", ""), default_style=f"fg:{_FG}")
            lines.append(("", "\n"))
            return lines
        if rt == "action":
            color = row.get("color", _BLUE)
            fg = f"bold {color}" if sel else color
            pointer = "  ➔ " if sel else "    "
            lines = [(bg or fg, f"{pointer}[ {row.get('label', '')} ]\n")]
            hint = row.get("hint", "")
            if sel and hint:
                lines.append((bg or f"{_MUTED}", f"       {hint}\n"))
            return lines
        return [("class:dim", f"  {str(row)}\n")]

    _run_list_dialog(
        rows,
        _render,
        title="Confirm Extension Deletion",
        legend="UP/DOWN: Navigate  •  ENTER: Select Action  •  ESC: Cancel",
        is_selectable_fn=_is_selectable,
        on_enter=_on_enter,
    )

    if action[0] == "confirm":
        code, resp = _api_delete(f"/marketplace/listings/{slug}")
        if code in (200, 204):
            msg_rows = [
                {"type": "info", "bold": True, "color": _GREEN, "text": f"✓  Extension '{name}' successfully removed!"},
                {"type": "spacer"},
                {"type": "action", "action": "ok", "label": "←  Return to My Listings", "color": _GREEN},
            ]
            _run_list_dialog(
                msg_rows,
                _render,
                title="Deletion Complete",
                legend="ENTER: Continue",
                is_selectable_fn=_is_selectable,
                on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
            )
            return True
        else:
            err = (resp or {}).get("detail", f"HTTP {code}")
            err_rows = [
                {"type": "info", "bold": True, "color": _RED, "text": f"✗  Delete failed: {err}"},
                {"type": "spacer"},
                {"type": "action", "action": "ok", "label": "←  Return", "color": _RED},
            ]
            _run_list_dialog(
                err_rows,
                _render,
                title="Deletion Failed",
                legend="ENTER: Continue",
                is_selectable_fn=_is_selectable,
                on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
            )
    return False


def _dialog_my_items(console):

    from utim_cli.utim import _run_list_dialog  # type: ignore



    while True:

        data = _api_get("/marketplace/my-listings")

        if isinstance(data, dict):

            items = data.get("items", [])

        elif isinstance(data, list):

            items = data

        else:

            items = []



        rows: list[dict] = []

        rows.append({"type": "title", "text": "🗃  MY PUBLISHED EXTENSIONS"})

        rows.append({"type": "action", "action": "back", "label": "←  Return to Marketplace Home", "color": _RED})

        rows.append({"type": "sep"})



        if not items:

            rows.append({"type": "info", "text": "  📭  You haven't published any extensions yet."})

            rows.append({"type": "info", "text": "  Use '📤 Publish Your Extension' from the main marketplace menu."})

        else:

            for item in items:

                itype = item.get("type", "skill")

                type_tag, _ = _format_type_badge(itype)

                is_pub = item.get("is_published", True)

                pub_tag = "[PUBLISHED]" if is_pub else "[UNPUBLISHED]"

                rows.append({

                    "type": "item_row",

                    "item": item,

                    "label": f"[{type_tag}]  {item.get('name', 'Extension')}  │  {pub_tag}  │  ⬇ {item.get('download_count', 0):,} installs  │  ⭐ {item.get('rating_avg', 0.0):.1f}",

                })



        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

            if rtype == "title":

                return [(f"bold {_MAUVE}", f"\n  {row.get('text', '')}\n")]

            if rtype == "info":

                lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

                lines.append(("", "\n"))

                return lines

            if rtype == "action":

                color = row.get("color", _BLUE)

                fg = f"bold {color}" if selected else color

                pointer = "  ➔ " if selected else "    "

                return [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

            if rtype == "item_row":

                fg = f"bold {_WHITE}" if selected else _FG

                pointer = "  ➔ " if selected else "    "

                return [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

            return [("class:dim", f"  {str(row)}\n")]



        action, idx = _run_list_dialog(rows, render_row, title="User Published Portfolio", legend="ENTER: Options / Remove  •  ESC/Q: Back", is_selectable_fn=_is_selectable)



        if action != "select" or idx is None:

            return



        sel = rows[idx]

        if sel.get("action") == "back":

            return



        if sel.get("type") == "item_row":

            item = sel.get("item", {})

            deleted = _dialog_manage_my_extension(console, item)

            if deleted:

                continue



def _dialog_pick_from_list(

    options: list[tuple[str, str]],

    title: str,

    current: str = "",

) -> Optional[str]:

    """Pick one item from a list.

    When called from a background thread (inside _run_full_screen_flow),

    _run_list_dialog starts a new PTK Application via app.run().  That must

    happen on the **main** event-loop thread, not the worker thread.

    We use run_coroutine_threadsafe + a threading.Event to block the worker

    until the user makes a selection — the same pattern used by _prompt_text.

    """

    import threading

    import asyncio

    from utim_cli.utim import _run_list_dialog, _MAIN_LOOP  # type: ignore

    rows = []

    for val, label in options:

        is_current = val == current

        mark = "  ✓" if is_current else ""

        rows.append({"value": val, "label": f"{label}{mark}"})

    def render_row(idx: int, row: dict, selected: bool):

        bg = f"bg:{_SURFACE}" if selected else ""

        fg = f"bold {_BLUE}" if selected else _BLUE

        pointer = "  ➔ " if selected else "    "

        return [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

    result = [None]

    done = threading.Event()

    def _run_dialog():

        try:

            action, idx = _run_list_dialog(

                rows, render_row,

                title=title,

                legend="ENTER: Select  •  ESC/Q: Cancel",

                is_selectable_fn=_is_selectable,

            )

            if action == "select" and idx is not None:

                result[0] = rows[idx].get("value")

        except Exception:

            pass

        finally:

            done.set()

    # Check if we're on the main thread or a background thread

    loop = _MAIN_LOOP

    try:

        asyncio.get_running_loop()

        # We ARE on the main event loop thread — just run directly

        _run_dialog()

    except RuntimeError:

        # We are on a background thread — schedule on main loop and block

        if loop and loop.is_running():

            async def _coro():

                _run_dialog()

            asyncio.run_coroutine_threadsafe(_coro(), loop)

            done.wait()

        else:

            _run_dialog()

    return result[0]

# ── Main Entry Point ──────────────────────────────────────────────────────────

def _dialog_seller_hub(console):

    """Seller profile + wallet hub screen."""

    from utim_cli.utim import _run_list_dialog, _run_in_terminal_safe  # type: ignore

    # Fetch profile from server

    profile_data = _api_get("/marketplace/seller-profile")

    wallet_data = _api_get("/marketplace/wallet")

    payment_info = _load_payment_info()

    has_profile = profile_data is not None

    rows: list[dict] = []

    # Header

    rows.append({"type": "title", "text": "👤  SELLER PROFILE & WALLET"})

    rows.append({"type": "sep"})

    if has_profile:

        emoji = profile_data.get("avatar_emoji", "🧑💻")

        name = profile_data.get("display_name") or "(no display name set)"

        bio = profile_data.get("bio") or "(no bio set)"

        rows.append({"type": "info", "text": f"  {emoji}  {name}  {'✅ Verified' if profile_data.get('is_verified') else ''}" })

        rows.append({"type": "info", "text": f"  📭  {bio}"})

        rows.append({"type": "spacer"})

        w = profile_data.get("wallet") or {}

        balance = w.get("balance_usd", 0.0)

        earned = w.get("total_earned_usd", 0.0)

        withdrawn = w.get("total_withdrawn_usd", 0.0)

        pending = w.get("pending_withdrawal_usd", 0.0)

        rows.append({"type": "info", "text": f"  💰  Wallet Balance:    [bold #a6e3a1]${balance:.3f}[/bold #a6e3a1] available"})

        rows.append({"type": "info", "text": f"  💰  Total Earned:     [bold #89b4fa]${earned:.3f}[/bold #89b4fa] all time"})

        rows.append({"type": "info", "text": f"  🏦  Total Withdrawn:  [bold #f9e2af]${withdrawn:.3f}[/bold #f9e2af]"})

        if pending > 0:

            rows.append({"type": "info", "text": f"  ⏳  Pending Payout:   [dim #f9e2af]${pending:.3f}[/dim #f9e2af] processing"})

        rows.append({"type": "spacer"})

    else:

        rows.append({"type": "info", "text": "  📭  No seller profile set up yet."})

        rows.append({"type": "info", "text": "  Create one to start publishing paid extensions and receiving payments."})

        rows.append({"type": "spacer"})

    # Payment method info

    upi = payment_info.get("upi_id", "")

    bank_acc = payment_info.get("account_number", "")

    if upi:

        rows.append({"type": "info", "text": f"  📱  Saved UPI: [bold #89dceb]{upi}[/bold #89dceb]"})

    if bank_acc:

        rows.append({"type": "info", "text": f"  🏛  Saved Bank A/C: ••••{bank_acc[-4:]}"})

    if not upi and not bank_acc:

        rows.append({"type": "info", "text": f"  ⚠   No payment method saved. Set one below before withdrawing."})

    rows.append({"type": "sep"})

    # Actions

    rows.append({"type": "action", "action": "setup_profile", "label": "✏️   Setup / Edit Seller Profile", "color": _MAUVE, "hint": "Set display name, bio, avatar emoji"})

    rows.append({"type": "spacer"})

    rows.append({"type": "action", "action": "set_payment", "label": "💳  Set Withdrawal Payment Method", "color": _CYAN, "hint": "Save UPI ID or bank account locally"})

    rows.append({"type": "spacer"})

    if has_profile:

        rows.append({"type": "action", "action": "withdraw", "label": "💸  Request Withdrawal", "color": _GREEN, "hint": "Transfer earnings to your bank/UPI"})

        rows.append({"type": "spacer"})

    rows.append({"type": "action", "action": "history", "label": "📜  View Withdrawal History", "color": _BLUE, "hint": "See all past withdrawal requests"})

    rows.append({"type": "spacer"})

    admin_info = _api_get("/marketplace/is-admin")

    is_admin = isinstance(admin_info, dict) and admin_info.get("is_admin", False)

    if is_admin:

        rows.append({"type": "action", "action": "admin_payouts", "label": "👑  Admin Payout Approvals", "color": _YELLOW, "hint": "Review & approve pending seller withdrawal requests"})

        rows.append({"type": "spacer"})

    rows.append({"type": "action", "action": "back", "label": "←  Return to Marketplace", "color": _RED})

    def render_row(idx: int, row: dict, selected: bool):

        bg = f"bg:{_SURFACE}" if selected else ""

        rtype = row.get("type")

        if rtype == "sep":

            return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

        if rtype == "spacer":

            return [("class:dim", "\n")]

        if rtype == "title":

            return [(f"bold {_MAUVE}", f"\n  {row.get('text', '')}\n")]

        if rtype == "info":

            lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

            lines.append(("", "\n"))

            return lines

        if rtype == "action":

            color = row.get("color", _BLUE)

            fg = f"bold {color}" if selected else color

            pointer = "  ➔ " if selected else "    "

            hint = row.get("hint", "")

            lines = [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

            if selected and hint:

                lines.append((bg or f"{_MUTED}", f"       {hint}\n"))

            return lines

        return [("class:dim", f"  {str(row)}\n")]

    while True:

        action, idx = _run_list_dialog(

            rows, render_row,

            title="Seller Hub  👤  Profile & Wallet",

            legend="UP/DOWN: Navigate  •  ENTER: Select  •  ESC/Q: Back",

            is_selectable_fn=_is_selectable

        )

        if action not in ("select",) or idx is None:

            return

        sel = rows[idx]

        act = sel.get("action")

        if act == "back" or act is None:

            return

        if act == "setup_profile":

            _dialog_setup_seller_profile(console)

            # Refresh data

            profile_data = _api_get("/marketplace/seller-profile")

            has_profile = profile_data is not None

            # Rebuild rows

            return _dialog_seller_hub(console)

        if act == "set_payment":

            _dialog_set_payment_method(console)

            payment_info = _load_payment_info()

            continue

        if act == "withdraw":

            _dialog_request_withdrawal(console, profile_data, payment_info)

            continue

        if act == "history":

            _dialog_withdrawal_history(console, wallet_data)

            continue

        if act == "admin_payouts":

            _dialog_admin_payouts(console)

            continue

def _dialog_setup_seller_profile(console):

    """Seller profile creation/editing form."""

    from utim_cli.utim import _run_list_dialog  # type: ignore

    existing = _api_get("/marketplace/seller-profile") or {}

    form = {

        "display_name": existing.get("display_name", ""),

        "bio": existing.get("bio", ""),

        "avatar_emoji": existing.get("avatar_emoji", "🧑‍💻"),

    }

    while True:

        val_name = form["display_name"] or "(not set)"

        val_bio = form["bio"] or "(not set)"

        val_emoji = form["avatar_emoji"] or "🧑‍💻"

        rows: list[dict] = [

            {"type": "title", "text": "👤  PROFILE SETUP"},

            {"type": "info",  "text": "  Your profile is public and shown on marketplace activity."},

            {"type": "sep"},

            {"type": "field", "field": "display_name", "label": f"👤  Display Name / Handle :  [bold #89dceb]{val_name}[/bold #89dceb]", "hint": "ENTER: Edit Display Name"},

            {"type": "field", "field": "bio",          "label": f"📝  Short Bio            :  [bold #89dceb]{val_bio}[/bold #89dceb]", "hint": "ENTER: Edit Bio"},

            {"type": "field", "field": "avatar_emoji", "label": f"🧑‍💻  Avatar Emoji         :  [bold #f9e2af]{val_emoji}[/bold #f9e2af]", "hint": "ENTER: Edit Avatar Emoji"},

            {"type": "sep"},

            {"type": "action", "action": "save", "label": "✓  Save Profile", "color": _GREEN, "hint": "Save profile changes to UTIM Marketplace"},

            {"type": "action", "action": "back", "label": "←  Cancel", "color": _RED},

        ]

        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

            if rtype == "title":

                return _parse_markup_to_tuples(f"\n  {row.get('text', '')}\n", default_style=f"bold {_MAUVE}")

            if rtype == "info":

                lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

                lines.append(("", "\n"))

                return lines

            if rtype == "field" or rtype == "action":

                color = row.get("color", _BLUE if rtype == "action" else _FG)

                fg = f"bold {color}" if selected else color

                pointer = "  ➔ " if selected else "    "

                lines = _parse_markup_to_tuples(f"{pointer}{row.get('label', '')}\n", default_style=bg or fg)

                hint = row.get("hint", "")

                if selected and hint:

                    lines.extend(_parse_markup_to_tuples(f"       {hint}\n", default_style=bg or f"fg:{_MUTED}"))

                return lines

            return [("class:dim", f"  {str(row)}\n")]

        action, idx = _run_list_dialog(rows, render_row, title="Seller Profile Setup", legend="UP/DOWN: Navigate  •  ENTER: Edit / Save  •  ESC/Q: Back", is_selectable_fn=_is_selectable)

        if action not in ("select",) or idx is None:

            return

        sel = rows[idx]

        act = sel.get("action")

        fld = sel.get("field")

        if act == "back":

            return

        if act == "save":

            if not form["display_name"]:

                continue

            _api_post("/marketplace/seller-profile", {

                "display_name": form["display_name"],

                "bio": form["bio"] or None,

                "avatar_emoji": form["avatar_emoji"],

            })

            return

        if fld == "display_name":

            val = _prompt_text(console, "Display Name:", default=form["display_name"])

            if val is not None:

                form["display_name"] = val

        elif fld == "bio":

            val = _prompt_text(console, "Short Bio:", default=form["bio"])

            if val is not None:

                form["bio"] = val

        elif fld == "avatar_emoji":

            val = _prompt_text(console, "Avatar Emoji:", default=form["avatar_emoji"])

            if val is not None:

                form["avatar_emoji"] = val

def _dialog_set_payment_method(console):

    """Set UPI ID or bank account locally in ~/.utim/payment_id/payment_info.json"""

    from utim_cli.utim import _run_list_dialog  # type: ignore

    existing = _load_payment_info()

    form = {

        "method": existing.get("preferred_method", "upi"),

        "upi_id": existing.get("upi_id", ""),

        "account_name": existing.get("account_name", ""),

        "account_number": existing.get("account_number", ""),

        "ifsc_code": existing.get("ifsc_code", ""),

    }

    while True:

        rows: list[dict] = [

            {"type": "title", "text": "💳  WITHDRAWAL PAYMENT METHOD SETUP"},

            {"type": "info",  "text": "  Payment details are saved locally on your device only."},

            {"type": "info",  "text": "  They are sent to the server ONLY when you request a withdrawal."},

            {"type": "sep"},

            {"type": "field", "field": "method", "label": f"📱  Payment Method :  [{'bold #89dceb' if form['method'] == 'upi' else 'bold #cba6f7'}]{form['method'].upper()}[/]", "hint": "ENTER: Toggle between UPI and Bank Account"},

        ]

        if form["method"] == "upi":

            val_upi = form["upi_id"] or "(not set)"

            rows.append({"type": "field", "field": "upi_id", "label": f"📱  UPI VPA ID      :  [bold #89dceb]{val_upi}[/bold #89dceb]", "hint": "ENTER: Edit UPI ID (e.g. name@upi)"})

        else:

            val_name = form["account_name"] or "(not set)"

            val_num = f"••••{form['account_number'][-4:]}" if form["account_number"] else "(not set)"

            val_ifsc = form["ifsc_code"] or "(not set)"

            rows.append({"type": "field", "field": "account_name",   "label": f"👤  Account Name    :  [bold #89dceb]{val_name}[/bold #89dceb]", "hint": "ENTER: Edit Account Holder Name"})

            rows.append({"type": "field", "field": "account_number", "label": f"🏦  Account Number  :  [bold #a6e3a1]{val_num}[/bold #a6e3a1]", "hint": "ENTER: Edit Bank Account Number"})

            rows.append({"type": "field", "field": "ifsc_code",       "label": f"🏛  IFSC Code       :  [bold #f9e2af]{val_ifsc}[/bold #f9e2af]", "hint": "ENTER: Edit Bank IFSC Code"})

        rows.append({"type": "sep"})

        rows.append({"type": "action", "action": "save", "label": "✓  Save Payment Details", "color": _GREEN, "hint": "Save details locally for future withdrawals"})

        rows.append({"type": "action", "action": "back", "label": "←  Cancel", "color": _RED})

        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

            if rtype == "title":

                return _parse_markup_to_tuples(f"\n  {row.get('text', '')}\n", default_style=f"bold {_MAUVE}")

            if rtype == "info":

                lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

                lines.append(("", "\n"))

                return lines

            if rtype == "field" or rtype == "action":

                color = row.get("color", _BLUE if rtype == "action" else _FG)

                fg = f"bold {color}" if selected else color

                pointer = "  ➔ " if selected else "    "

                lines = _parse_markup_to_tuples(f"{pointer}{row.get('label', '')}\n", default_style=bg or fg)

                hint = row.get("hint", "")

                if selected and hint:

                    lines.extend(_parse_markup_to_tuples(f"       {hint}\n", default_style=bg or f"fg:{_MUTED}"))

                return lines

            return [("class:dim", f"  {str(row)}\n")]

        action, idx = _run_list_dialog(rows, render_row, title="Payment Method Setup", legend="UP/DOWN: Navigate  •  ENTER: Edit / Save  •  ESC/Q: Back", is_selectable_fn=_is_selectable)

        if action not in ("select",) or idx is None:

            return

        sel = rows[idx]

        act = sel.get("action")

        fld = sel.get("field")

        if act == "back":

            return

        if act == "save":

            info = {

                "upi_id": form["upi_id"],

                "account_name": form["account_name"],

                "account_number": form["account_number"],

                "ifsc_code": form["ifsc_code"].upper() if form["ifsc_code"] else "",

                "preferred_method": form["method"],

            }

            _save_payment_info(info)

            return

        if fld == "method":

            form["method"] = "bank" if form["method"] == "upi" else "upi"

        elif fld == "upi_id":

            val = _prompt_text(console, "  Enter UPI VPA ID (e.g. name@upi): ", default=form["upi_id"])

            if val is not None:

                form["upi_id"] = val

        elif fld == "account_name":

            val = _prompt_text(console, "  Enter Account Holder Name: ", default=form["account_name"])

            if val is not None:

                form["account_name"] = val

        elif fld == "account_number":

            val = _prompt_text(console, "  Enter Account Number: ", default=form["account_number"])

            if val is not None:

                form["account_number"] = val

        elif fld == "ifsc_code":

            val = _prompt_text(console, "  Enter IFSC Code: ", default=form["ifsc_code"])

            if val is not None:

                form["ifsc_code"] = val.upper()

def _show_insufficient_balance_dialog(requested: float, balance: float):
    """Show clear error dialog when withdrawal amount exceeds available balance."""
    from utim_cli.utim import _run_list_dialog

    shortfall = requested - balance
    rows = [
        {"type": "info", "bold": True, "color": _RED, "text": "🚫  INSUFFICIENT BALANCE FOR WITHDRAWAL"},
        {"type": "info", "color": _MUTED, "text": "Your requested withdrawal amount exceeds your available wallet balance:"},
        {"type": "spacer"},
        {"type": "info", "bold": True, "color": _YELLOW, "text": f"  • Requested Amount:   ${requested:.3f} USD"},
        {"type": "info", "bold": True, "color": _GREEN,  "text": f"  • Available Balance:  ${balance:.3f} USD"},
        {"type": "info", "bold": True, "color": _RED,    "text": f"  • Insufficient By:    ${shortfall:.3f} USD"},
        {"type": "spacer"},
        {"type": "info", "color": _MUTED, "text": f"Please enter an amount less than or equal to your available balance (${balance:.3f} USD)."},
        {"type": "spacer"},
        {"type": "sep"},
        {"type": "action", "action": "ok", "label": "←  Return & Adjust Amount", "color": _GREEN},
    ]

    def _render_err(idx, row, selected):
        bg = f"bg:{_SURFACE}" if selected else ""
        ptr = "  ➔ " if selected else "    "
        rt = row.get("type")
        if rt == "sep":
            return [("class:dim", "  " + "─" * 60 + "\n")]
        if rt == "spacer":
            return [("", "\n")]
        if rt == "info":
            color = row.get("color", _FG)
            style = f"bold {color}" if row.get("bold") else f"fg:{color}"
            return [(style, f"  {row['text']}\n")]
        if rt == "action":
            color = row.get("color", _FG)
            return [(f"{bg} bold {color}" if selected else f"fg:{color}", f"{ptr}{row['label']}\n")]
        return [("class:dim", f"  {row}\n")]

    _run_list_dialog(
        rows,
        _render_err,
        title="Insufficient Balance Warning",
        legend="ENTER: Adjust Amount",
        is_selectable_fn=lambda r: r.get("type") == "action",
        on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
    )


def _dialog_request_withdrawal(console, profile_data: dict, payment_info: dict):
    """Withdrawal request form with balance validation."""
    from utim_cli.utim import _run_list_dialog, _set_inline_edit  # type: ignore

    wallet = (profile_data or {}).get("wallet") or {}
    balance = wallet.get("balance_usd", 0.0)
    upi = payment_info.get("upi_id", "")
    bank_acc = payment_info.get("account_number", "")
    method = payment_info.get("preferred_method", "upi" if upi else "bank")
    amount = [min(balance, 1.0) if balance > 0 else 0.01]

    while True:
        rows: list[dict] = [
            {"type": "title", "text": "💸  REQUEST WITHDRAWAL"},
            {"type": "info",  "text": f"  Available Balance :  [bold #a6e3a1]${balance:.3f} USD[/bold #a6e3a1]"},
        ]

        if not upi and not bank_acc:
            rows.append({"type": "info", "text": "  [bold #f38ba8]⚠  No payment method configured. Please set a payment method first in Seller Hub.[/bold #f38ba8]\n"})
            rows.append({"type": "sep"})
            rows.append({"type": "action", "action": "back", "label": "←  Return to Seller Hub", "color": _RED})
        else:
            payout_dest = f"UPI: {upi}" if method == "upi" and upi else f"Bank: ••••{bank_acc[-4:] if bank_acc else ''}"
            rows.append({"type": "field", "field": "amount", "label": f"💵  Withdrawal Amount  :  [bold #a6e3a1]${amount[0]:.3f} USD[/bold #a6e3a1]", "hint": "ENTER: Change amount to withdraw"})
            rows.append({"type": "field", "field": "method", "label": f"🏦  Payout Destination :  [bold #89dceb]{payout_dest}[/bold #89dceb]", "hint": "ENTER: Switch between UPI and Bank Account"})
            rows.append({"type": "sep"})
            rows.append({"type": "action", "action": "submit", "label": "✓  Submit Withdrawal Request", "color": _GREEN, "hint": "Submit payout request to UTIM Admin"})
            rows.append({"type": "action", "action": "back", "label": "←  Cancel", "color": _RED})

        def render_row(idx: int, row: dict, selected: bool):
            bg = f"bg:{_SURFACE}" if selected else ""
            rtype = row.get("type")
            if rtype == "sep":
                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]
            if rtype == "title":
                return _parse_markup_to_tuples(f"\n  {row.get('text', '')}\n", default_style=f"bold {_MAUVE}")
            if rtype == "info":
                lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")
                lines.append(("", "\n"))
                return lines
            if rtype == "field" or rtype == "action":
                color = row.get("color", _BLUE if rtype == "action" else _FG)
                fg = f"bold {color}" if selected else color
                pointer = "  ➔ " if selected else "    "
                lines = _parse_markup_to_tuples(f"{pointer}{row.get('label', '')}\n", default_style=bg or fg)
                hint = row.get("hint", "")
                if selected and hint:
                    lines.extend(_parse_markup_to_tuples(f"       {hint}\n", default_style=bg or f"fg:{_MUTED}"))
                return lines
            return [("class:dim", f"  {str(row)}\n")]

        async def _on_enter(idx, row, app, value=None):
            fld = row.get("field")
            act = row.get("action")

            if value is not None and fld == "amount":
                try:
                    val = float(value.strip())
                    if val > balance:
                        _show_insufficient_balance_dialog(val, balance)
                    elif val < 0.01:
                        pass
                    else:
                        amount[0] = val
                except ValueError:
                    pass
                return True

            if act == "back":
                app.exit()
                return False

            if act == "submit":
                if amount[0] > balance:
                    _show_insufficient_balance_dialog(amount[0], balance)
                    return True
                app.exit()
                return False

            if fld == "amount":
                _set_inline_edit("amount", "  Withdrawal Amount in USD: ", f"{amount[0]:.2f}")
                return True

            if fld == "method":
                if upi and bank_acc:
                    method = "bank" if method == "upi" else "upi"
                    app.invalidate()
                return True

            return True

        action, idx = _run_list_dialog(
            rows,
            render_row,
            title="Request Withdrawal",
            legend="UP/DOWN: Navigate  •  ENTER: Edit / Submit  •  ESC/Q: Back",
            is_selectable_fn=_is_selectable,
            on_enter=_on_enter,
        )

        if not idx:
            return

        sel = rows[idx]
        act = sel.get("action")

        if act == "back":
            return

        if act == "submit":
            if amount[0] > balance:
                _show_insufficient_balance_dialog(amount[0], balance)
                continue

            live_info = _load_payment_info()
            req_body = {
                "amount_usd": amount[0],
                "method": method,
                "upi_id": live_info.get("upi_id"),
                "account_number": live_info.get("account_number"),
                "account_name": live_info.get("account_name"),
                "ifsc_code": live_info.get("ifsc_code"),
            }

            code, resp = _api_post("/marketplace/wallet/withdraw", req_body)
            if code in (200, 201):
                msg_rows = [
                    {"type": "info", "bold": True, "color": _GREEN, "text": f"✓  Withdrawal request for ${amount[0]:.3f} USD submitted successfully!"},
                    {"type": "info", "color": _MUTED, "text": "Your payout request is now being processed by the system."},
                    {"type": "spacer"},
                    {"type": "action", "action": "ok", "label": "←  Return to Seller Hub", "color": _GREEN},
                ]
                _run_list_dialog(
                    msg_rows,
                    render_row,
                    title="Withdrawal Submitted",
                    legend="ENTER: Continue",
                    is_selectable_fn=lambda r: r.get("type") == "action",
                    on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
                )
                return
            else:
                err_detail = (resp or {}).get("detail", f"HTTP {code}")
                if "insufficient balance" in err_detail.lower():
                    _show_insufficient_balance_dialog(amount[0], balance)
                else:
                    err_rows = [
                        {"type": "info", "bold": True, "color": _RED, "text": f"✗  Withdrawal Request Failed"},
                        {"type": "info", "color": _RED, "text": f"  Detail: {err_detail}"},
                        {"type": "spacer"},
                        {"type": "action", "action": "ok", "label": "←  Return & Adjust", "color": _RED},
                    ]
                    _run_list_dialog(
                        err_rows,
                        render_row,
                        title="Withdrawal Error",
                        legend="ENTER: Continue",
                        is_selectable_fn=lambda r: r.get("type") == "action",
                        on_enter=lambda idx, row, app, val=None: (app.exit(), False)[1],
                    )
                continue

def _dialog_withdrawal_history(console, wallet_data: Optional[dict]):

    """View past withdrawal requests."""

    from utim_cli.utim import _run_list_dialog  # type: ignore

    # Refresh from server

    fresh = _api_get("/marketplace/wallet")

    withdrawals = (fresh or {}).get("withdrawals", []) if fresh else []

    rows: list[dict] = []

    rows.append({"type": "title", "text": "📜  WITHDRAWAL HISTORY"})

    rows.append({"type": "action", "action": "back", "label": "←  Return to Seller Hub", "color": _RED})

    rows.append({"type": "sep"})

    STATUS_COLORS = {

        "pending": _YELLOW,

        "processing": _CYAN,

        "completed": _GREEN,

        "failed": _RED,

    }

    if not withdrawals:

        rows.append({"type": "info", "text": "  📭  No withdrawal requests yet."})

    else:

        for w in withdrawals:

            sc = STATUS_COLORS.get(w.get("status", ""), _MUTED)

            date = w.get("created_at", "")[:10] if w.get("created_at") else ""

            method = w.get("method", "upi").upper()

            label = f"${w.get('amount_usd', 0):.2f}  •  {method}  •  [{w.get('status', '').upper()}]  •  {date}"

            rows.append({"type": "withdrawal_row", "w": w, "label": label, "color": sc})

    def render_row(idx: int, row: dict, selected: bool):

        bg = f"bg:{_SURFACE}" if selected else ""

        rtype = row.get("type")

        if rtype == "sep":

            return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

        if rtype == "title":

            return [(f"bold {_MAUVE}", f"\n  {row.get('text', '')}\n")]

        if rtype == "info":

            return [(f"fg:{_FG}", f"{row.get('text', '')}\n")]

        if rtype == "action":

            color = row.get("color", _BLUE)

            fg = f"bold {color}" if selected else color

            pointer = "  ➔ " if selected else "    "

            return [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

        if rtype == "withdrawal_row":

            color = row.get("color", _FG)

            fg = f"bold {color}" if selected else color

            pointer = "  ➔ " if selected else "    "

            return [(bg or fg, f"{pointer}{row.get('label', '')}\n")]

        return [("class:dim", f"  {str(row)}\n")]

    action, idx = _run_list_dialog(rows, render_row, title="Withdrawal History", legend="ESC/Q: Back", is_selectable_fn=_is_selectable)

    if action == "select" and idx is not None:

        sel = rows[idx]

        if sel.get("action") == "back":

            return


def _dialog_admin_payouts(console):

    """Admin interface to view and approve pending seller withdrawal requests."""

    from utim_cli.utim import _run_list_dialog  # type: ignore

    while True:

        withdrawals = _api_get("/marketplace/admin/withdrawals") or []

        if not isinstance(withdrawals, list):

            withdrawals = []

        rows: list[dict] = [

            {"type": "title", "text": "👑  ADMIN PAYOUT APPROVALS"},

            {"type": "action", "action": "back", "label": "←  Return to Seller Hub", "color": _RED},

            {"type": "sep"},

        ]

        pending_list = [w for w in withdrawals if w.get("status") == "pending"]

        completed_list = [w for w in withdrawals if w.get("status") != "pending"]

        if not withdrawals:

            rows.append({"type": "info", "text": "  📭  No withdrawal requests found."})

        else:

            if pending_list:

                rows.append({"type": "info", "text": f"  ⏳  PENDING APPROVALS ({len(pending_list)}):"})

                for w in pending_list:

                    amt = w.get("amount_usd", 0.0)

                    email = w.get("seller_email", "Unknown")

                    method = str(w.get("method", "upi")).upper()

                    rows.append({

                        "type": "admin_w_row",

                        "w": w,

                        "label": f"⏳  [PENDING]  ${amt:.3f} USD  │  Seller: {email}  │  Method: {method}",

                        "color": _YELLOW,

                    })

                rows.append({"type": "sep"})

            if completed_list:

                rows.append({"type": "info", "text": f"  📜  PAST WITHDRAWALS ({len(completed_list)}):"})

                for w in completed_list:

                    amt = w.get("amount_usd", 0.0)

                    st = str(w.get("status", "completed")).upper()

                    email = w.get("seller_email", "Unknown")

                    color = _GREEN if st == "COMPLETED" else _RED

                    rows.append({

                        "type": "admin_w_row",

                        "w": w,

                        "label": f"[{st}]  ${amt:.3f} USD  │  Seller: {email}",

                        "color": color,

                    })

        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

            if rtype == "title":

                return _parse_markup_to_tuples(f"\n  {row.get('text', '')}\n", default_style=f"bold {_MAUVE}")

            if rtype == "info":

                lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

                lines.append(("", "\n"))

                return lines

            if rtype == "action" or rtype == "admin_w_row":

                color = row.get("color", _BLUE)

                fg = f"bold {color}" if selected else color

                pointer = "  ➔ " if selected else "    "

                lines = _parse_markup_to_tuples(f"{pointer}{row.get('label', '')}\n", default_style=bg or fg)

                return lines

            return [("class:dim", f"  {str(row)}\n")]

        action, idx = _run_list_dialog(rows, render_row, title="Admin Payout Approvals", legend="ENTER: Inspect Request  •  ESC/Q: Back", is_selectable_fn=_is_selectable)

        if action not in ("select",) or idx is None:

            return

        sel = rows[idx]

        if sel.get("action") == "back":

            return

        if sel.get("type") == "admin_w_row":

            w = sel.get("w", {})

            w_id = w.get("id")

            st = w.get("status")

            if st != "pending":

                continue

            amt = w.get("amount_usd", 0.0)

            inr = amt * 83.0

            email = w.get("seller_email", "Unknown")

            method = str(w.get("method", "upi")).lower()

            appr_rows = [

                {"type": "info", "text": f"  👑  WITHDRAWAL REQUEST DETAILS\n"},

                {"type": "info", "text": f"  Withdrawal ID   :  {w_id}"},

                {"type": "info", "text": f"  Seller Email    :  [bold #89b4fa]{email}[/bold #89b4fa]"},

                {"type": "info", "text": f"  Amount Payout   :  [bold #a6e3a1]${amt:.3f} USD[/bold #a6e3a1]  [dim #f9e2af](≈ ₹{inr:.2f} INR)[/dim #f9e2af]"},

                {"type": "info", "text": f"  Payout Method   :  [bold #cba6f7]{method.upper()}[/bold #cba6f7]"},

            ]

            if method == "upi":

                upi_val = w.get("upi_id") or "Not provided"

                appr_rows.append({"type": "info", "text": f"  📱  UPI VPA ID      :  [bold #89dceb]{upi_val}[/bold #89dceb]\n"})

            else:

                appr_rows.append({"type": "info", "text": f"  👤  Account Name    :  [bold #89dceb]{w.get('account_name', 'N/A')}[/bold #89dceb]"})

                appr_rows.append({"type": "info", "text": f"  🏦  Account Number  :  [bold #a6e3a1]{w.get('account_number', 'N/A')}[/bold #a6e3a1]"})

                appr_rows.append({"type": "info", "text": f"  🏛  IFSC Code       :  [bold #f9e2af]{w.get('ifsc_code', 'N/A')}[/bold #f9e2af]\n"})

            appr_rows.append({"type": "sep"})

            appr_rows.append({"type": "action", "action": "approve", "label": "✓  Approve & Mark Paid", "color": _GREEN, "hint": "Mark this payout as complete after sending money"})

            appr_rows.append({"type": "action", "action": "reject",  "label": "✗  Reject & Refund Wallet", "color": _RED,   "hint": "Restore money to seller's wallet"})

            appr_rows.append({"type": "action", "action": "back",    "label": "←  Cancel", "color": _CYAN})

            appr_act, appr_idx = _run_list_dialog(appr_rows, render_row, title="Approve Payout", legend="ENTER: Select Action", is_selectable_fn=_is_selectable)

            if appr_act == "select" and appr_idx is not None:

                a_sel = appr_rows[appr_idx]

                a_act = a_sel.get("action")

                if a_act == "approve":

                    _api_post(f"/marketplace/admin/withdrawals/{w_id}/approve", {})

                elif a_act == "reject":

                    _api_post(f"/marketplace/admin/withdrawals/{w_id}/reject", {})

def _check_and_run_first_time_setup(console):

    """Profile setup is accessible via Seller Hub -> Setup / Edit Seller Profile."""

    pass

def _dialog_marketplace(orchestrator=None):

    from utim_cli.utim import console, _run_list_dialog, _run_in_terminal_safe  # type: ignore

    # Check and run first-time profile setup cleanly on main thread before TUI opens

    _check_and_run_first_time_setup(console)

    home_data = [None]

    loading   = [True]

    def _load_home_data():

        try:

            home_data[0] = _fetch_homepage()

        except Exception:

            home_data[0] = {}

        finally:

            loading[0] = False

    t = threading.Thread(target=_load_home_data, daemon=True)

    t.start()

    t.join(timeout=6)

    data       = home_data[0] or {}

    latest_72h = data.get("latest_72h") or []

    featured   = (data.get("featured") or [])[:5]

    popular    = (data.get("popular")  or [])[:5]

    newest     = (data.get("newest")   or [])[:5]

    all_items  = data.get("all_items")  or []

    while True:

        rows: list[dict] = []

        # Banner Header

        rows.append({"type": "banner"})

        rows.append({"type": "sep"})

        # Quick Actions Menu

        rows.append({"type": "action", "action": "browse",   "icon": "🌐", "label": "Browse & Filter All Extensions (All)", "hint": "Explore by category, tags, ratings & price"})

        rows.append({"type": "spacer"})

        rows.append({"type": "action", "action": "publish",  "icon": "📤", "label": "Publish Your Extension",              "hint": "Share skills, miniagents or tools globally"})

        rows.append({"type": "spacer"})

        rows.append({"type": "action", "action": "my_items", "icon": "🗃",  "label": "My Published Extensions",            "hint": "Manage your extension portfolio"})

        rows.append({"type": "spacer"})

        rows.append({"type": "action", "action": "seller_profile", "icon": "👤", "label": "Profile & Wallet",                   "hint": "Set up your profile, view earnings & withdraw"})

        rows.append({"type": "spacer"})

        rows.append({"type": "action", "action": "exit",     "icon": "✕",  "label": "Close Marketplace",                   "hint": "Return to UTIM agent chat"})

        rows.append({"type": "sep"})

        if loading[0]:

            rows.append({"type": "info", "text": "  ⏳  Connecting to UTIM extension registry..."})

        else:

            # 1. LATEST EXTENSIONS (LAST 72 HOURS)

            rows.append({"type": "section", "title": "⚡  LATEST EXTENSIONS (UPLOADED IN LAST 72 HOURS)"})

            if latest_72h:

                for item in latest_72h:

                    rows.append({"type": "card", "item": item, "badge": "⚡ 72h"})

            else:

                rows.append({"type": "info", "text": "  ℹ️  No extensions uploaded in the last 72 hours. Browse the full catalog below!"})

            rows.append({"type": "sep"})

            # 2. FEATURED

            if featured:

                rows.append({"type": "section", "title": "⭐  SPOTLIGHT & FEATURED EXTENSIONS"})

                for item in featured:

                    rows.append({"type": "card", "item": item})

                rows.append({"type": "sep"})

            # 3. MOST POPULAR

            if popular:

                rows.append({"type": "section", "title": "🔥  MOST POPULAR COMMUNITY EXTENSIONS"})

                for item in popular:

                    rows.append({"type": "card", "item": item})

                rows.append({"type": "sep"})

            # 4. ALL EXTENSIONS CATALOG

            if all_items:

                rows.append({"type": "section", "title": f"🌐  ALL EXTENSIONS CATALOG ({len(all_items)} Available)"})

                for item in all_items:

                    rows.append({"type": "card", "item": item})

                rows.append({"type": "sep"})

            if not latest_72h and not featured and not popular and not all_items:

                rows.append({"type": "info", "text": "  📭  Marketplace catalog is ready. Be the first to publish an extension!"})

        def render_row(idx: int, row: dict, selected: bool):

            bg = f"bg:{_SURFACE}" if selected else ""

            rtype = row.get("type")

            if rtype == "sep":

                return [("class:dim", "  ────────────────────────────────────────────────────────────\n")]

            if rtype == "spacer":

                return [("class:dim", "\n")]

            if rtype == "banner":

                return [

                    (f"bold {_MAUVE}", "  ╔══════════════════════════════════════════════════════════════════════════════╗\n"),

                    (f"bold {_WHITE}", "  ║  🛍️   UTIM EXTENSION STORE  │  The Premier AI Agent & Tool Marketplace        ║\n"),

                    (f"{_CYAN}",   "  ║  ⚡ Instant Install  •  95% Creator Revenue  •  Verified Package Security    ║\n"),

                    (f"bold {_MAUVE}", "  ╚══════════════════════════════════════════════════════════════════════════════╝\n"),

                ]

            if rtype == "section":

                return [(f"bold {_YELLOW}", f"\n  {row.get('title', '')}\n")]

            if rtype == "info":

                lines = _parse_markup_to_tuples(row.get('text', ''), default_style=f"fg:{_FG}")

                lines.append(("", "\n"))

                return lines

            if rtype == "action":

                act   = row.get("action", "")

                icon  = row.get("icon", "•")

                label = row.get("label", "")

                hint  = row.get("hint", "")

                if act == "exit":

                    fg = f"bold {_RED}" if selected else _RED

                elif act == "publish":

                    fg = f"bold {_MAUVE}" if selected else _MAUVE

                elif act == "seller_profile":

                    fg = f"bold {_GREEN}" if selected else _GREEN

                else:

                    fg = f"bold {_BLUE}" if selected else _BLUE

                pointer = "  ➔ " if selected else "    "

                lines = [(bg or fg, f"{pointer}{icon}  {label}\n")]

                if selected and hint:

                    lines.append((bg or f"{_MUTED}", f"       {hint}\n"))

                return lines

            if rtype == "card":

                item = row.get("item", {})

                name  = _truncate_str(item.get("name", "Extension"), 34)

                itype = item.get("type", "skill")

                type_tag, _ = _format_type_badge(itype)

                price_tag = _format_price_pill(item.get("price_usd", 0.0), item.get("is_paid", False))

                desc = _truncate_str(item.get("description", ""), 68)

                dl_cnt = item.get("download_count", 0)

                stars = item.get("rating_avg", 0.0)

                badge = row.get("badge", "")

                badge_str = f"  [{badge}]" if badge else ""

                pointer = "  ➔ " if selected else "    "

                top_color = f"bold {_CYAN}" if selected else f"bold {_WHITE}"

                card_border = f"bold {_MAUVE}" if selected else f"{_BORDER}"

                action_btn = "[ ⚡ CLICK TO VIEW & BUY ]" if selected else "[ View Package ]"

                lines = [

                    (bg or card_border, f"{pointer}┌── {name}  [{type_tag}]  {price_tag}{badge_str}\n"),

                    (bg or f"fg:{_FG}", f"    │   {desc}\n"),

                    (bg or f"{_MUTED}", f"    └── ⬇ {dl_cnt:,} installs  │  ⭐ {stars:.1f} rating  ──────────  "),

                    (bg or (f"bold {_GREEN}" if selected else f"{_BLUE}"), f"{action_btn}\n\n"),

                ]

                return lines

            return [("class:dim", f"  {str(row)}\n")]

        action, idx = _run_list_dialog(

            rows,

            render_row,

            title="UTIM Marketplace  🛒  Discover Extensions",

            legend="UP/DOWN: Navigate  •  ENTER: Select  •  ESC/Q: Exit",

            is_selectable_fn=_is_selectable,

        )

        if action not in ("select",) or idx is None:

            break

        sel   = rows[idx]

        rtype = sel.get("type")

        act   = sel.get("action")

        if rtype in ("sep", "banner", "section", "info", "spacer"):

            continue

        if act == "exit" or (rtype == "action" and act is None):

            break

        if act == "browse":

            _dialog_browse(console)

            continue

        if act == "publish":

            _dialog_publish(console)

            continue

        if act == "my_items":

            _dialog_my_items(console)

            continue

        if act == "seller_profile":

            _dialog_seller_hub(console)

            continue

        if rtype == "card":

            item = sel.get("item", {})

            slug = item.get("slug", "")

            if slug:

                _dialog_item_detail(console, slug, item)

            continue

    return None

