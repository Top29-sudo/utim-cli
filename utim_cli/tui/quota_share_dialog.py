"""
Quota Share TUI Dialog
----------------------
Multi-step interactive flow for sharing credits with referred users.

Steps:
  1. Balance overview + referred user list
  2. Select recipient
  3. Enter amount
  4. Preview / transfer summary
  5. Confirm or cancel
  6. Success / failure result
"""
from __future__ import annotations

from typing import Optional


# ── Colour constants (matching UTIM palette) ─────────────────────────────────
_CYAN   = "#42bcf5"
_GREEN  = "#50fa7b"
_YELLOW = "#f9e2af"
_RED    = "#ff5555"
_PURPLE = "#cba6f7"
_DIM    = "dim"

BAR_WIDTH = 36


def _fmt_credits(n: float) -> str:
    """Format a credit number with thousands separators and 2 dp."""
    return f"{n:,.2f}"


def _progress_bar(value: float, total: float, width: int = BAR_WIDTH) -> str:
    """Return a Unicode block progress bar string."""
    pct = min(1.0, max(0.0, value / total)) if total > 0 else 0.0
    filled = int(round(pct * width))
    return "█" * filled + "░" * (width - filled)


def _bar_color(pct: float) -> str:
    if pct >= 50:
        return "bold green"
    elif pct >= 20:
        return "bold yellow"
    return "bold red"


# ── Public entry point ────────────────────────────────────────────────────────

def run_quota_share_flow(orchestrator) -> None:
    """Launch the full multi-step quota sharing flow from the / menu."""
    from utim_cli.utim import console, _run_list_dialog, _flush_stdin_buffer
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests

    api_key = config.get("api_key")
    if not api_key:
        console.print("\n  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
        return

    headers = {"X-API-Key": api_key}

    # ── Step 1: Fetch share info from server ─────────────────────────────────
    console.print(f"\n  [bold {_CYAN}]⟳ Fetching quota share info...[/bold {_CYAN}]", end=" ")
    try:
        resp = requests.get(f"{SERVER_URL}/api/quota-share/info", headers=headers, timeout=10)
        if resp.status_code == 403:
            console.print()
            msg = resp.json().get("detail", "Quota sharing is not available on your current plan.")
            console.print(f"\n  [bold {_RED}]✗ {msg}[/bold {_RED}]\n")
            return
        resp.raise_for_status()
        info = resp.json()
    except requests.exceptions.RequestException as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Failed to connect to UTIM server: {exc}[/bold {_RED}]\n")
        return
    except Exception as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Error: {exc}[/bold {_RED}]\n")
        return

    console.print("[bold green]Done![/bold green]")

    referred_users = info.get("referred_users", [])
    shareable_balance = float(info.get("shareable_balance", 0.0))
    quota_bank = float(info.get("quota_bank", 0.0))
    current_cycle_balance = float(info.get("current_cycle_balance", 0.0))
    unallocated = float(info.get("unallocated", 0.0))
    remaining_cycles = int(info.get("remaining_cycles", 0))
    regular_plan_credits = float(info.get("regular_plan_credits", 0.0))
    plan_name = info.get("plan_name", "Unknown")

    # ── Show balance overview ─────────────────────────────────────────────────
    _show_balance_overview(
        console, plan_name, shareable_balance, quota_bank,
        current_cycle_balance, unallocated, remaining_cycles, regular_plan_credits
    )

    if not referred_users:
        console.print(f"\n  [bold {_YELLOW}] You have no directly referred users eligible to receive credits directly.[/bold {_YELLOW}]")
        console.print(f"  [dim]You can still convert credits to a redeem code for yourself or future referees.[/dim]\n")

    if shareable_balance <= 0:
        console.print(f"\n  [bold {_RED}]✗ You have no shareable credits available.[/bold {_RED}]\n")
        return

    # ── Step 2: Select recipient or redeem code option ────────────────────────
    choices = [
        {
            "uid": "redeem_code_only",
            "display_name": "Create Redeem Code",
            "email_hint": "Generate a code that you or any referee can redeem via /redeem",
        }
    ] + referred_users

    def render_user_row(i, row, sel):
        bg = f"bg:#313244 fg:#ffffff bold" if sel else ""
        prefix = f"  ➔ " if sel else "     "
        if row["uid"] == "redeem_code_only":
            name_style = bg or f"bold {_PURPLE}"
        else:
            name_style = bg or f"bold {_CYAN}"
        return [
            (bg or "white", prefix),
            (name_style, f"{row['display_name']}\n"),
            (bg or "class:dim", f"       {row['email_hint']}\n"),
        ]

    action, idx = _run_list_dialog(
        choices,
        render_user_row,
        title="Quota Share — Select Recipient or Action",
        legend="↑↓ Navigate  Enter Select  q/Esc Cancel",
    )

    if action != "select" or idx is None:
        console.print("\n  [dim]Quota share cancelled.[/dim]\n")
        return

    recipient = choices[idx]
    recipient_uid = recipient["uid"]
    recipient_name = recipient["display_name"]

    # ── Step 3: Enter amount ──────────────────────────────────────────────────
    amount = _prompt_amount(console, shareable_balance, recipient_name)
    if amount is None:
        console.print("\n  [dim]Quota share cancelled.[/dim]\n")
        return

    # ── Step 4: Preview (dry-run) ─────────────────────────────────────────────
    console.print(f"\n  [bold {_CYAN}]⟳ Calculating transfer preview...[/bold {_CYAN}]", end=" ")
    try:
        prev_resp = requests.post(
            f"{SERVER_URL}/api/quota-share/preview",
            json={"recipient_uid": recipient_uid, "amount": amount},
            headers=headers,
            timeout=10,
        )
        if not prev_resp.ok:
            console.print()
            msg = prev_resp.json().get("detail", "Preview failed.")
            console.print(f"\n  [bold {_RED}]✗ {msg}[/bold {_RED}]\n")
            return
        preview = prev_resp.json()
    except Exception as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Preview error: {exc}[/bold {_RED}]\n")
        return

    console.print("[bold green]Done![/bold green]")

    # ── Step 5: Show summary + confirm ────────────────────────────────────────
    confirmed = _show_transfer_summary_and_confirm(console, preview)

    if not confirmed:
        console.print("\n  [dim]Transfer cancelled.[/dim]\n")
        return

    # ── Step 6: Execute transfer ──────────────────────────────────────────────
    console.print(f"\n  [bold {_CYAN}]⟳ Executing transfer...[/bold {_CYAN}]", end=" ")
    try:
        tx_resp = requests.post(
            f"{SERVER_URL}/api/quota-share/transfer",
            json={"recipient_uid": recipient_uid, "amount": amount},
            headers=headers,
            timeout=15,
        )
        if not tx_resp.ok:
            console.print()
            msg = tx_resp.json().get("detail", "Transfer failed.")
            console.print(f"\n  [bold {_RED}]✗ Transfer failed: {msg}[/bold {_RED}]\n")
            return
        result = tx_resp.json()
    except Exception as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Transfer error: {exc}[/bold {_RED}]\n")
        return

    console.print("[bold green]Done![/bold green]")

    # ── Step 7: Success screen ────────────────────────────────────────────────
    _show_success(console, result, plan_name, regular_plan_credits)


# ── Helper UI functions ───────────────────────────────────────────────────────

def _show_balance_overview(
    console, plan_name: str, shareable_balance: float, quota_bank: float,
    current_cycle_balance: float, unallocated: float,
    remaining_cycles: int, regular_plan_credits: float
) -> None:
    """Renders the shareable credit breakdown panel."""
    from rich.panel import Panel
    from rich.align import Align

    width = 56
    console.print()
    console.print(Panel(
        Align.center(f"[bold {_CYAN}]QUOTA SHARE — {plan_name} Plan[/bold {_CYAN}]"),
        border_style=_CYAN,
        expand=False,
        width=width
    ))
    console.print()

    # Total shareable
    pct_total = min(100.0, (shareable_balance / regular_plan_credits * 100.0)) if regular_plan_credits > 0 else 0.0
    bar = _progress_bar(shareable_balance, regular_plan_credits)
    bar_col = _bar_color(pct_total)
    console.print(f"  [bold white]Total Shareable Credits[/bold white]")
    console.print(f"  [[{bar_col}]{bar}[/{bar_col}]] [{bar_col}]{pct_total:.1f}%[/{bar_col}]")
    console.print(f"  [bold {_GREEN}]{_fmt_credits(shareable_balance)}[/bold {_GREEN}] credits available to share\n")

    # Sources breakdown
    console.print(f"  [bold {_YELLOW}]Credit Sources[/bold {_YELLOW}]")

    def _source_row(label: str, value: float, icon: str = "•"):
        pct = min(100.0, (value / regular_plan_credits * 100.0)) if regular_plan_credits > 0 else 0.0
        bar_s = _progress_bar(value, regular_plan_credits, width=24)
        col = _bar_color(pct)
        console.print(f"  {icon} [bold white]{label}[/bold white]")
        console.print(f"    [[{col}]{bar_s}[/{col}]] [bold {_GREEN}]{_fmt_credits(value)}[/bold {_GREEN}] [dim]credits[/dim]")

    _source_row("Quota Bank", quota_bank, "")
    _source_row("Current Cycle Balance", current_cycle_balance, "⏱")
    _source_row("Unallocated Plan Credits", unallocated, "")

    if remaining_cycles > 0 and unallocated > 0:
        per_cycle = unallocated / remaining_cycles
        console.print(f"\n  [dim]Future cycle quota: [bold white]{_fmt_credits(per_cycle)}[/bold white] credits/cycle · {remaining_cycles} cycles remaining[/dim]")

    console.print()


# ── safe prompt helper ────────────────────────────────────────────────────────

def _safe_prompt(prompt_text: str) -> str:
    """Bulletproof terminal input helper to avoid nested prompt_toolkit event loop issues."""
    import sys
    out_stream = sys.__stdout__ if sys.__stdout__ else sys.stdout
    out_stream.write(prompt_text)
    out_stream.flush()
    try:
        if sys.__stdin__ and hasattr(sys.__stdin__, "readline"):
            val = sys.__stdin__.readline()
            if not val:
                raise EOFError()
            return val.rstrip('\r\n')
        else:
            return input()
    except (KeyboardInterrupt, EOFError):
        raise KeyboardInterrupt


def _prompt_amount(console, max_amount: float, recipient_name: str) -> Optional[float]:
    """
    Interactive prompt to enter a transfer amount.
    Returns the validated float, or None if the user cancels.
    """

    if recipient_name == "Create Redeem Code":
        console.print(f"  [bold white]Action:[/bold white] [bold {_PURPLE}]Create Redeem Code[/bold {_PURPLE}]")
    else:
        console.print(f"  [bold white]Recipient:[/bold white] [bold {_CYAN}]{recipient_name}[/bold {_CYAN}]")
    console.print(f"  [bold white]Available:[/bold white] [bold {_GREEN}]{_fmt_credits(max_amount)}[/bold {_GREEN}] shareable credits\n")

    while True:
        try:
            prompt_label = "convert" if recipient_name == "Create Redeem Code" else "share"
            raw = _safe_prompt(
                f"  Enter credits to {prompt_label} (1 – {_fmt_credits(max_amount)}, or 'cancel'): "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            return None

        if raw.lower() in ("cancel", "q", "exit", "quit", ""):
            return None

        # Strip commas for convenience
        raw_clean = raw.replace(",", "").replace(" ", "")
        try:
            value = float(raw_clean)
        except ValueError:
            console.print(f"  [bold {_RED}]✗ Invalid number. Please try again.[/bold {_RED}]")
            continue

        if value <= 0:
            console.print(f"  [bold {_RED}]✗ Amount must be greater than zero.[/bold {_RED}]")
            continue

        if value > max_amount:
            console.print(
                f"  [bold {_RED}]✗ Amount exceeds your shareable balance "
                f"({_fmt_credits(max_amount)} credits).[/bold {_RED}]"
            )
            continue

        return value


def _show_transfer_summary_and_confirm(console, preview: dict) -> bool:
    """
    Renders the transfer summary panel and asks for confirmation.
    Returns True if the user confirms, False to cancel.
    """

    deductions = preview.get("deductions", {})
    recipient = preview.get("recipient", {})
    amount = float(preview.get("amount", 0.0))
    from_bank = float(deductions.get("from_quota_bank", 0.0))
    from_cycle = float(deductions.get("from_current_cycle", 0.0))
    from_unallocated = float(deductions.get("from_unallocated", 0.0))
    remaining_shareable = float(preview.get("remaining_shareable", 0.0))
    remaining_unallocated = float(preview.get("remaining_unallocated", 0.0))
    new_cycle_quota = preview.get("new_cycle_quota")
    remaining_cycles = int(preview.get("remaining_cycles", 0))
    regular_plan_credits = float(preview.get("regular_plan_credits", 0.0))
    plan_name = preview.get("plan_name", "")

    width = 56

    console.print()
    from rich.panel import Panel
    from rich.align import Align
    console.print(Panel(
        Align.center(f"[bold {_YELLOW}]TRANSFER SUMMARY[/bold {_YELLOW}]"),
        border_style=_YELLOW,
        expand=False,
        width=width
    ))
    console.print()

    is_direct = recipient.get("uid") != "redeem_code_only"
    if is_direct:
        console.print(f"  [bold white]Recipient[/bold white]         [bold {_CYAN}]{recipient.get('display_name', 'Unknown')}[/bold {_CYAN}]")
        console.print(f"  [bold white]Transfer Amount[/bold white]   [bold {_GREEN}]{_fmt_credits(amount)} credits[/bold {_GREEN}]")
    else:
        console.print(f"  [bold white]Action[/bold white]            [bold {_PURPLE}]Create Redeem Code[/bold {_PURPLE}]")
        console.print(f"  [bold white]Amount[/bold white]            [bold {_GREEN}]{_fmt_credits(amount)} credits[/bold {_GREEN}]")
    console.print()
    console.print(f"  [bold {_YELLOW}]Deduction Breakdown[/bold {_YELLOW}]")

    def _deduct_row(label: str, value: float):
        if value > 0:
            console.print(f"    [dim]•[/dim] [bold white]{label}[/bold white]   [bold {_RED}]-{_fmt_credits(value)}[/bold {_RED}]")

    _deduct_row("Quota Bank", from_bank)
    _deduct_row("Current Cycle Balance", from_cycle)
    _deduct_row("Unallocated Plan Credits", from_unallocated)

    console.print()
    console.print(f"  [bold white]Remaining Shareable[/bold white]  [bold {_CYAN}]{_fmt_credits(remaining_shareable)} credits[/bold {_CYAN}]")

    if from_unallocated > 0:
        console.print()
        console.print(f"  [bold {_YELLOW}]⟳ Future Cycle Recalculation[/bold {_YELLOW}]")
        console.print(f"    [dim]Remaining unallocated:[/dim] [bold white]{_fmt_credits(remaining_unallocated)}[/bold white] credits")
        console.print(f"    [dim]Remaining cycles:[/dim] [bold white]{remaining_cycles}[/bold white]")
        if new_cycle_quota is not None:
            console.print(f"    [dim]New credits per cycle:[/dim] [bold {_GREEN}]{_fmt_credits(new_cycle_quota)}[/bold {_GREEN}]")

        # Unallocated bar
        if regular_plan_credits > 0:
            pct = min(100.0, (remaining_unallocated / regular_plan_credits) * 100.0)
            bar = _progress_bar(remaining_unallocated, regular_plan_credits)
            col = _bar_color(pct)
            console.print(f"\n    [dim]Unallocated bar after transfer:[/dim]")
            console.print(f"    [[{col}]{bar}[/{col}]] [{col}]{pct:.1f}%[/{col}]")
            console.print(f"    [dim]{_fmt_credits(remaining_unallocated)} / {_fmt_credits(regular_plan_credits)} · {plan_name}[/dim]")

    console.print()
    console.print("─" * width, style=_DIM)
    console.print()

    while True:
        try:
            ans = _safe_prompt(
                "  Confirm transfer? (yes / no): "
            ).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return False

        if ans in ("yes", "y"):
            return True
        elif ans in ("no", "n", "cancel", "q", ""):
            return False
        else:
            console.print(f"  [dim]Please enter [bold]yes[/bold] or [bold]no[/bold].[/dim]")


def _show_success(console, result: dict, plan_name: str, regular_plan_credits: float) -> None:
    """Renders the post-transfer success screen with the redeem code."""
    amount = float(result.get("amount", 0.0))
    recipient = result.get("recipient", {})
    deductions = result.get("deductions", {})
    new_cycle_quota = result.get("new_cycle_quota")
    remaining_shareable = float(result.get("remaining_shareable", 0.0))
    remaining_unallocated = float(result.get("remaining_unallocated", 0.0))
    remaining_cycles = int(result.get("remaining_cycles", 0))
    transfer_id = result.get("transfer_id", "")
    redeem_code = result.get("redeem_code", "")
    from_unallocated = float(deductions.get("from_unallocated", 0.0))

    width = 56

    is_direct = result.get("direct_transfer", False)

    width = 56

    console.print()
    from rich.panel import Panel
    from rich.align import Align
    if is_direct:
        console.print(Panel(
            Align.center(f"[bold {_GREEN}]TRANSFER SUCCESSFUL[/bold {_GREEN}]"),
            border_style=_GREEN,
            expand=False,
            width=width
        ))
        console.print()
        console.print(f"  [bold {_GREEN}]✓ {_fmt_credits(amount)} credits shared directly with {recipient.get('display_name', 'recipient')}[/bold {_GREEN}]")
    else:
        console.print(Panel(
            Align.center(f"[bold {_PURPLE}]REDEEM CODE GENERATED[/bold {_PURPLE}]"),
            border_style=_PURPLE,
            expand=False,
            width=width
        ))
        console.print()
        console.print(f"  [bold {_GREEN}]✓ {_fmt_credits(amount)} credits converted to a claimable redeem code.[/bold {_GREEN}]")
    console.print()
    
    if not is_direct and redeem_code:
        console.print("  [bold white]Redeem Code:[/bold white]")
        console.print(f"  [bold {_PURPLE}]┌─────────────────────────────────────────┐[/bold {_PURPLE}]")
        console.print(f"  [bold {_PURPLE}]│[/bold {_PURPLE}]  [bold white]{redeem_code}[/bold white]  [bold {_PURPLE}]│[/bold {_PURPLE}]")
        console.print(f"  [bold {_PURPLE}]└─────────────────────────────────────────┘[/bold {_PURPLE}]")
        console.print(f"  [dim]Share this code with your referee, or run [/dim][bold {_CYAN}]/redeem[/bold {_CYAN}][dim] to use it yourself.[/dim]")
        console.print()

    console.print(f"  [bold white]Deducted from:[/bold white]")
    if float(deductions.get("from_quota_bank", 0.0)) > 0:
        console.print(f"    • Quota Bank: [bold]{_fmt_credits(deductions['from_quota_bank'])}[/bold]")
    if float(deductions.get("from_current_cycle", 0.0)) > 0:
        console.print(f"    • Current Cycle: [bold]{_fmt_credits(deductions['from_current_cycle'])}[/bold]")
    if from_unallocated > 0:
        console.print(f"    • Unallocated Credits: [bold]{_fmt_credits(from_unallocated)}[/bold]")

    console.print()
    console.print(f"  [dim]Remaining shareable balance: [bold {_CYAN}]{_fmt_credits(remaining_shareable)}[/bold {_CYAN}] credits[/dim]")

    if from_unallocated > 0 and new_cycle_quota is not None:
        pct = min(100.0, (remaining_unallocated / regular_plan_credits) * 100.0) if regular_plan_credits > 0 else 0.0
        bar = _progress_bar(remaining_unallocated, regular_plan_credits)
        col = _bar_color(pct)
        console.print()
        console.print(f"  [bold {_YELLOW}]Unallocated Monthly Quota (updated)[/bold {_YELLOW}]")
        console.print(f"  [[{col}]{bar}[/{col}]] [{col}]{pct:.1f}%[/{col}]")
        console.print(
            f"  [dim]{_fmt_credits(remaining_unallocated)} / {_fmt_credits(regular_plan_credits)} credits · "
            f"{remaining_cycles} cycles left · {_fmt_credits(new_cycle_quota)} per cycle[/dim]"
        )

    if transfer_id:
        console.print(f"\n  [dim]Transfer ID: {transfer_id}[/dim]")

    console.print()
