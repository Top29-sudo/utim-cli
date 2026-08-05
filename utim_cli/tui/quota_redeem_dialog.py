"""
Quota Redeem TUI Dialog
-----------------------
Flow for pasting/typing and claiming a redeem code to add credits to bonus quota.
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


def _fmt_credits(n: float) -> str:
    """Format a credit number with thousands separators and 2 dp."""
    return f"{n:,.2f}"


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


def run_quota_redeem_flow(orchestrator) -> None:
    """Launch the interactive flow to redeem a credit code."""
    from utim_cli.utim import console
    from utim_cli.config import config
    from utim_cli.auth import SERVER_URL
    import requests

    api_key = config.get("api_key")
    if not api_key:
        console.print("\n  [bold red]✗ No API key found.[/bold red] Please run [bold]utim login[/bold] first.\n")
        return

    headers = {"X-API-Key": api_key}
    width = 56

    console.print()
    from rich.panel import Panel
    from rich.align import Align
    console.print(Panel(
        Align.center(f"[bold {_PURPLE}]🎁 REDEEM CODE[/bold {_PURPLE}]"),
        border_style=_PURPLE,
        expand=False,
        width=width
    ))
    console.print()

    # Step 1: Input Code
    try:
        code_input = _safe_prompt("  Enter redeem code (or 'cancel'): ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n  [dim]Cancelled.[/dim]\n")
        return

    if not code_input or code_input.lower() in ("cancel", "q", "exit", "quit"):
        console.print("\n  [dim]Cancelled.[/dim]\n")
        return

    # Normalize code format (e.g. upper case, trim spaces)
    code = code_input.upper()

    # Step 2: Fetch code info from server
    console.print(f"\n  [bold {_CYAN}]⟳ Verifying code info...[/bold {_CYAN}]", end=" ")
    try:
        resp = requests.get(f"{SERVER_URL}/api/quota-share/redeem/{code}", headers=headers, timeout=10)
        if resp.status_code == 404:
            console.print()
            console.print(f"\n  [bold {_RED}]✗ Invalid code. Please double check and try again.[/bold {_RED}]\n")
            return
        elif resp.status_code == 403:
            console.print()
            msg = resp.json().get("detail", "You are not eligible to claim this code.")
            console.print(f"\n  [bold {_RED}]✗ {msg}[/bold {_RED}]\n")
            return
        elif resp.status_code == 409:
            console.print()
            console.print(f"\n  [bold {_RED}]✗ This code has already been redeemed.[/bold {_RED}]\n")
            return

        resp.raise_for_status()
        code_info = resp.json()
    except requests.exceptions.RequestException as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Failed to connect to UTIM server: {exc}[/bold {_RED}]\n")
        return
    except Exception as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Verification error: {exc}[/bold {_RED}]\n")
        return

    console.print("[bold green]Verified![/bold green]")

    amount = float(code_info.get("amount", 0.0))
    sender_name = code_info.get("sender_name", "Unknown")

    console.print()
    console.print("─" * width, style=_DIM)
    console.print(f"  [bold white]Source/Sender:[/bold white]   [bold {_CYAN}]{sender_name}[/bold {_CYAN}]")
    console.print(f"  [bold white]Value:[/bold white]           [bold {_GREEN}]{_fmt_credits(amount)} credits[/bold {_GREEN}]")
    console.print(f"  [dim]Note: Redeeming adds these credits to your Bonus Quota (never expires).[/dim]")
    console.print("─" * width, style=_DIM)
    console.print()

    # Step 3: Confirmation
    while True:
        try:
            ans = _safe_prompt("  Redeem this code? (yes / no): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  [dim]Cancelled.[/dim]\n")
            return

        if ans in ("yes", "y"):
            break
        elif ans in ("no", "n", "cancel", "q", ""):
            console.print("\n  [dim]Redemption cancelled.[/dim]\n")
            return
        else:
            console.print(f"  [dim]Please enter [bold]yes[/bold] or [bold]no[/bold].[/dim]")

    # Step 4: Execute Redeem
    console.print(f"\n  [bold {_CYAN}]⟳ Claiming credits...[/bold {_CYAN}]", end=" ")
    try:
        claim_resp = requests.post(
            f"{SERVER_URL}/api/quota-share/redeem",
            json={"code": code},
            headers=headers,
            timeout=15
        )
        if not claim_resp.ok:
            console.print()
            msg = claim_resp.json().get("detail", "Failed to claim code.")
            console.print(f"\n  [bold {_RED}]✗ Redemption failed: {msg}[/bold {_RED}]\n")
            return
        result = claim_resp.json()
    except Exception as exc:
        console.print()
        console.print(f"\n  [bold {_RED}]✗ Claim error: {exc}[/bold {_RED}]\n")
        return

    console.print("[bold green]Claimed![/bold green]")

    # Success screen
    credits_added = float(result.get("credits_added", 0.0))
    new_bonus = float(result.get("new_bonus_balance", 0.0))
    capped = result.get("capped", False)

    console.print()
    from rich.panel import Panel
    from rich.align import Align
    console.print(Panel(
        Align.center(f"[bold {_GREEN}]🎉 REDEMPTION SUCCESSFUL[/bold {_GREEN}]"),
        border_style=_GREEN,
        expand=False,
        width=width
    ))
    console.print()
    console.print(f"  [bold {_GREEN}]✓ successfully added {_fmt_credits(credits_added)} credits to your Bonus Quota.[/bold {_GREEN}]")
    if capped:
        console.print(f"  [dim yellow]⚠ The amount was capped to your plan's maximum Bonus Quota limit.[/dim yellow]")
    console.print(f"  [dim]Your updated Bonus Quota balance is now [bold {_GREEN}]{_fmt_credits(new_bonus)}[/bold {_GREEN}] credits.[/dim]")
    console.print()
