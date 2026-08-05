import requests
import datetime
import json
from utim_cli.config import config
from utim_cli.auth import SERVER_URL
from utim_cli.constants import ARROW_SYMBOL


# ─── Consent dialog ───────────────────────────────────────────────────────────

def _dialog_consent_share_chat(run_list_dialog):
    """
    Shows a full-screen consent prompt asking whether the user allows UTIM to
    collect their chat history to help improve the product.

    Returns:
        True  – user consented (default / Allow selected)
        False – user declined (Don't Allow selected)
        None  – user cancelled the entire feedback flow
    """
    consent_rows = [
        {
            "key": "allow",
            "label": "✅  Allow  (Recommended)",
            "desc": "Share this session's chat history — helps UTIM improve responses",
        },
        {
            "key": "deny",
            "label": "🚫  Don't Allow",
            "desc": "Submit only your star rating & comment — no chat data sent",
        },
        {
            "key": "cancel",
            "label": "Cancel",
            "desc": "Exit without submitting feedback",
        },
    ]

    def _render_consent(idx, row, selected):
        bg = "bg:#1e1e2e" if selected else ""
        if row["key"] == "cancel":
            fg = "bold #f38ba8" if selected else "#f38ba8"
        elif row["key"] == "allow":
            fg = "bold #a6e3a1" if selected else "#a6e3a1"
        else:
            fg = "bold #f9e2af" if selected else "#f9e2af"
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['label']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    action, idx = run_list_dialog(
        consent_rows,
        _render_consent,
        title="Data Consent — Help Improve UTIM",
        legend="ENTER to confirm · ESC/Q to cancel  |  Default: Allow",
    )

    if action != "select":
        return None
    key = consent_rows[idx]["key"]
    if key == "cancel":
        return None
    return key == "allow"


# ─── /rate — manual feedback submission ───────────────────────────────────────

def _dialog_submit_feedback(orchestrator=None):
    from utim_cli.utim import _run_list_dialog, console
    from prompt_toolkit import prompt

    api_key = config.get("api_key")

    # ── Step 1: Star rating ──────────────────────────────────────────────────
    rating_rows = [
        {"key": "5", "label": "⭐⭐⭐⭐⭐  Excellent", "desc": "Perfect response, resolved task perfectly"},
        {"key": "4", "label": "⭐⭐⭐⭐  Good",      "desc": "Good response, small issues"},
        {"key": "3", "label": "⭐⭐⭐  Average",     "desc": "Okay response, needed manual corrections"},
        {"key": "2", "label": "⭐⭐  Poor",          "desc": "Struggled with the task, lazy/empty response"},
        {"key": "1", "label": "⭐  Terrible",        "desc": "Completely failed, crashed or hung"},
        {"key": "cancel", "label": "Cancel",          "desc": "Exit without submitting"},
    ]

    def _render_rating(idx, row, selected):
        bg = "bg:#1e1e2e" if selected else ""
        fg = (
            ("bold #f38ba8" if selected else "#f38ba8")
            if row["key"] == "cancel"
            else ("bold #a6e3a1" if selected else "#a6e3a1")
        )
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['label']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    action, idx = _run_list_dialog(
        rating_rows, _render_rating,
        title="Rate the Last Response",
        legend="ENTER to select, ESC/Q to cancel",
    )
    if action != "select" or rating_rows[idx]["key"] == "cancel":
        console.print("\n  [yellow]Feedback cancelled.[/yellow]\n")
        return

    rating = int(rating_rows[idx]["key"])

    # ── Step 2: Optional comment (always shown) ──────────────────────────────
    console.print(
        "\n  [bold #89b4fa]Write a comment about this response "
        "(press Enter to leave blank):[/bold #89b4fa]"
    )
    try:
        comment = prompt("  ✍  Comment: ").strip() or None
    except (KeyboardInterrupt, EOFError):
        comment = None

    # ── Step 3: Consent ──────────────────────────────────────────────────────
    share_chat = _dialog_consent_share_chat(_run_list_dialog)
    if share_chat is None:
        console.print("\n  [yellow]Feedback cancelled.[/yellow]\n")
        return

    chat_history = None
    if share_chat and orchestrator and hasattr(orchestrator, "messages"):
        chat_history = orchestrator.messages

    # ── Step 4: Submit ───────────────────────────────────────────────────────
    console.print("\n  [dim]Submitting feedback...[/dim]")
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        resp = requests.post(
            f"{SERVER_URL}/feedback/submit",
            json={"rating": rating, "comment": comment, "chat_history": chat_history},
            headers=headers,
            timeout=10,
            verify=config.verify_ssl,
        )
        if resp.status_code == 200:
            console.print(
                "  [bold green]✓ Thank you for your feedback! "
                "It helps improve UTIM.[/bold green]\n"
            )
            if rating < 4 and chat_history:
                try:
                    from utim_cli.reflection import analyze_poor_feedback_async
                    analyze_poor_feedback_async(chat_history, comment)
                except Exception:
                    pass
        else:
            console.print(
                f"  [bold red]✗ Failed to submit feedback "
                f"(HTTP {resp.status_code}): {resp.text}[/bold red]\n"
            )
    except Exception as e:
        console.print(
            f"  [bold red]✗ Network error while submitting feedback: {e}[/bold red]\n"
        )


# ─── Auto-triggered conditional feedback (post long-run) ─────────────────────

def _dialog_submit_feedback_conditional(orchestrator=None):
    from utim_cli.utim import _run_list_dialog, console
    from prompt_toolkit import prompt

    api_key = config.get("api_key")

    # ── Step 1: Thumbs Up / Down ─────────────────────────────────────────────
    thumbs_rows = [
        {"key": "up",     "label": "👍  Thumbs Up",   "desc": "The response was good or average"},
        {"key": "down",   "label": "👎  Thumbs Down", "desc": "The response was average, poor, or terrible"},
        {"key": "cancel", "label": "Cancel",           "desc": "Skip feedback submission"},
    ]

    def _render_thumbs(idx, row, selected):
        bg = "bg:#1e1e2e" if selected else ""
        if row["key"] == "cancel":
            fg = "bold #f38ba8" if selected else "#f38ba8"
        elif row["key"] == "up":
            fg = "bold #a6e3a1" if selected else "#a6e3a1"
        else:
            fg = "bold #f9e2af" if selected else "#f9e2af"
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['label']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    action, idx = _run_list_dialog(
        thumbs_rows, _render_thumbs,
        title="Rate UTIM's Long-Running Execution",
        legend="How was UTIM's response for this long run? (ENTER to select)",
    )
    if action != "select" or thumbs_rows[idx]["key"] == "cancel":
        return

    is_up = thumbs_rows[idx]["key"] == "up"

    # ── Step 2: Detailed star rating filtered by thumbs ──────────────────────
    if is_up:
        rows = [
            {"key": "5", "label": "⭐⭐⭐⭐⭐  Excellent", "desc": "Perfect response, resolved task perfectly"},
            {"key": "4", "label": "⭐⭐⭐⭐  Good",      "desc": "Good response, small issues"},
            {"key": "3", "label": "⭐⭐⭐  Average",     "desc": "Okay response, needed manual corrections"},
        ]
    else:
        rows = [
            {"key": "3", "label": "⭐⭐⭐  Average", "desc": "Okay response, needed manual corrections"},
            {"key": "2", "label": "⭐⭐  Poor",      "desc": "Struggled with the task, lazy/empty response"},
            {"key": "1", "label": "⭐  Terrible",    "desc": "Completely failed, crashed or hung"},
        ]
    rows.append({"key": "cancel", "label": "Cancel", "desc": "Exit without submitting"})

    def _render_rating(idx, row, selected):
        bg = "bg:#1e1e2e" if selected else ""
        fg = (
            ("bold #f38ba8" if selected else "#f38ba8")
            if row["key"] == "cancel"
            else ("bold #a6e3a1" if selected else "#a6e3a1")
        )
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['label']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    action, idx = _run_list_dialog(
        rows, _render_rating,
        title="Select Detailed Rating",
        legend="ENTER to select, ESC/Q to cancel",
    )
    if action != "select" or rows[idx]["key"] == "cancel":
        console.print("\n  [yellow]Feedback cancelled.[/yellow]\n")
        return

    rating = int(rows[idx]["key"])

    # ── Step 3: Optional comment ─────────────────────────────────────────────
    comment = None
    if rating != 5:
        console.print(
            "\n  [bold #89b4fa]Write a feedback comment describing the experience "
            "(press Enter to leave blank):[/bold #89b4fa]"
        )
        try:
            comment = prompt("  ✍  Comment: ").strip() or None
        except (KeyboardInterrupt, EOFError):
            comment = None

    # ── Step 4: Consent ──────────────────────────────────────────────────────
    share_chat = _dialog_consent_share_chat(_run_list_dialog)
    if share_chat is None:
        console.print("\n  [yellow]Feedback cancelled.[/yellow]\n")
        return

    chat_history = None
    if share_chat and orchestrator and hasattr(orchestrator, "messages"):
        chat_history = orchestrator.messages

    # ── Step 5: Submit ───────────────────────────────────────────────────────
    console.print("\n  [dim]Submitting feedback...[/dim]")
    headers = {"X-API-Key": api_key} if api_key else {}
    try:
        resp = requests.post(
            f"{SERVER_URL}/feedback/submit",
            json={"rating": rating, "comment": comment, "chat_history": chat_history},
            headers=headers,
            timeout=10,
            verify=config.verify_ssl,
        )
        if resp.status_code == 200:
            console.print(
                "  [bold green]✓ Thank you for your feedback! "
                "It helps improve UTIM.[/bold green]\n"
            )
        else:
            console.print(
                f"  [bold red]✗ Failed to submit feedback "
                f"(HTTP {resp.status_code}): {resp.text}[/bold red]\n"
            )
    except Exception as e:
        console.print(
            f"  [bold red]✗ Network error while submitting feedback: {e}[/bold red]\n"
        )


# ─── /feedbacks — admin browser ───────────────────────────────────────────────

def _dialog_feedbacks(orchestrator=None):
    from utim_cli.utim import _run_list_dialog, console
    from rich.rule import Rule

    api_key = config.get("api_key")
    if not api_key:
        console.print(
            "\n  [bold red]✗ Authentication Required.[/bold red] Please log in first.\n"
        )
        return

    # Load feedbacks from server
    console.print("\n  [dim]Fetching feedbacks from UTIM server...[/dim]")
    try:
        resp = requests.get(
            f"{SERVER_URL}/feedback/list",
            headers={"X-API-Key": api_key},
            timeout=15,
            verify=config.verify_ssl,
        )
        if resp.status_code == 403:
            console.print(
                "  [bold red]✗ Access Denied. Only authorized Firebase accounts "
                "can view feedbacks.[/bold red]\n"
            )
            return
        elif resp.status_code != 200:
            console.print(
                f"  [bold red]✗ Failed to retrieve feedbacks "
                f"(HTTP {resp.status_code}): {resp.text}[/bold red]\n"
            )
            return
    except Exception as e:
        console.print(f"  [bold red]✗ Network error while fetching feedbacks: {e}[/bold red]\n")
        return

    feedbacks = resp.json()
    if not feedbacks:
        console.print("\n  [yellow]No user feedbacks found.[/yellow]\n")
        from utim_cli.utim import wait_for_enter
        wait_for_enter("  Press Enter to return...")
        return

    # Build list rows
    rows = []
    for idx, fb in enumerate(feedbacks):
        stars    = "⭐" * fb["rating"]
        date_str = fb["created_at"].split(".")[0].replace("T", " ")
        email    = fb["user_email"]
        comment  = fb["comment"] or "(No comment)"
        chat_tag = "  💬" if fb.get("chat_history") else ""
        rows.append({
            "key":   str(idx),
            "label": f"{stars}{chat_tag}  by {email}  ({date_str})",
            "desc":  comment,
        })

    rows.append({"key": "back", "label": "Back to Chat", "desc": "Return to the main chat screen"})

    def _render(idx, row, selected):
        bg = "bg:#1e1e2e" if selected else ""
        fg = (
            ("bold #f38ba8" if selected else "#f38ba8")
            if row["key"] == "back"
            else ("bold #cba6f7" if selected else "#cba6f7")
        )
        return [
            (bg, "  ➔ " if selected else "    "),
            (bg or fg, f"{row['label']}\n"),
            (bg or "class:dim", f"      {row['desc']}\n"),
        ]

    while True:
        action, idx = _run_list_dialog(
            rows, _render,
            title="User Feedbacks Dashboard",
            legend="ENTER to view details · ESC/Q to return  |  💬 = includes chat history",
        )
        if action != "select" or rows[idx]["key"] == "back":
            return

        selected_fb = feedbacks[int(rows[idx]["key"])]

        def print_chat_history(con, fb=selected_fb):
            from rich.markup import escape
            con.print(f"\n  [bold #cba6f7]Feedback details:[/bold #cba6f7]")
            con.print(f"  [bold]User:[/bold]         {escape(str(fb['user_email']))}")
            con.print(f"  [bold]Date:[/bold]         {fb['created_at'].replace('T', ' ').split('.')[0]}")
            con.print(f"  [bold]Rating:[/bold]       {'⭐' * fb['rating']}")
            con.print(f"  [bold]Comment:[/bold]      {escape(str(fb['comment'] or '(None)'))}\n")
            con.print(Rule(style="dim"))
            con.print(f"\n  [bold #89b4fa]Chat History:[/bold #89b4fa]\n")

            chat = fb.get("chat_history")
            if isinstance(chat, str):
                try:
                    chat = json.loads(chat)
                except Exception:
                    chat = None

            if not isinstance(chat, list):
                con.print("  [dim italic](User did not consent to share chat history "
                          "or no history was captured)[/dim italic]\n")
                return

            for msg in chat:
                if not isinstance(msg, dict):
                    continue
                role    = msg.get("role", "unknown") or "unknown"
                content = msg.get("content") or ""
                if role == "user":
                    con.print(f"  [bold #42bcf5]👤 User:[/bold #42bcf5]")
                    con.print(f"    {escape(str(content))}\n")
                elif role == "assistant":
                    con.print(f"  [bold #a6e3a1]🤖 Assistant:[/bold #a6e3a1]")
                    if isinstance(content, list):
                        content = "\n".join(
                            p.get("text", "") for p in content if isinstance(p, dict)
                        )
                    con.print(f"    {escape(str(content))}\n")
                else:
                    con.print(f"  [dim]⚙  {role.title()}:[/dim]")
                    con.print(f"    {escape(str(content))}\n")

        from utim_cli.utim import _run_captured_dialog
        _run_captured_dialog(
            f"Chat History for {selected_fb['user_email']}", print_chat_history
        )
