"""
UTIM CLI Rewards Wheel TUI
──────────────────────────
Interactive Rich/Prompt Toolkit terminal UI for the UTIM Rewards Wheel.
Displays spin HUD, active 24h reward countdown, interactive model omission manager,
live probability table, and animated Wheel of Fortune spin.
"""

import time
import sys
import math
import random
import requests
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.prompt import Prompt, Confirm

from ..auth import get_auth_headers, get_api_url

console = Console()


def clean_model_display_name(raw_name: str, model_id: str = "") -> str:
    """Format model name cleanly by stripping provider prefixes and :free suffixes."""
    name = raw_name or model_id or ""
    if "/" in name:
        name = name.split("/")[-1]
    if name.lower().endswith(":free"):
        name = name[:-5]
    return name.strip()


def _fetch_rewards_status(api_base: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Fetch current rewards status from server."""
    resp = requests.get(f"{api_base}/api/rewards/status", headers=headers, timeout=10)
    if resp.status_code != 200:
        err_msg = "Unknown error"
        try:
            err_msg = resp.json().get("detail", resp.text)
        except Exception:
            err_msg = resp.text
        raise RuntimeError(f"Server returned status {resp.status_code}: {err_msg}")
    return resp.json()


def _preview_omissions(api_base: str, headers: Dict[str, str], omitted_models: List[str]) -> Dict[str, Any]:
    """Preview updated probabilities for selected omissions."""
    resp = requests.post(
        f"{api_base}/api/rewards/preview-omissions",
        headers=headers,
        json={"omitted_models": omitted_models},
        timeout=10
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Preview failed: {resp.text}")
    return resp.json()


def _confirm_snapshot(api_base: str, headers: Dict[str, str], omitted_models: List[str]) -> Dict[str, Any]:
    """Confirm probability snapshot on server."""
    resp = requests.post(
        f"{api_base}/api/rewards/confirm-snapshot",
        headers=headers,
        json={"omitted_models": omitted_models},
        timeout=10
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Snapshot confirmation failed: {resp.text}")
    return resp.json()


def _perform_spin(api_base: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """Execute server-authoritative wheel spin."""
    resp = requests.post(f"{api_base}/api/rewards/spin", headers=headers, timeout=15)
    if resp.status_code != 200:
        err_msg = "Spin failed"
        try:
            err_msg = resp.json().get("detail", resp.text)
        except Exception:
            err_msg = resp.text
        raise RuntimeError(err_msg)
    return resp.json()


def animate_terminal_wheel(winning_name: str, winning_category: str):
    """Animate a high-energy ASCII Wheel of Fortune spinning in the terminal."""
    wheel_frames = [
        "[bold cyan]╔════ UTIM REWARDS WHEEL ════╗[/bold cyan]\n    [yellow]► [1] Claude 3.7 | [2] GPT-4.5 | [3] DeepSeek R1 ◄[/yellow]",
        "[bold cyan]╔════ UTIM REWARDS WHEEL ════╗[/bold cyan]\n    [green]► [2] GPT-4.5 | [3] DeepSeek R1 | [4] Qwen 2.5 ◄[/green]",
        "[bold cyan]╔════ UTIM REWARDS WHEEL ════╗[/bold cyan]\n    [magenta]► [3] DeepSeek R1 | [4] Qwen 2.5 | [5] Gemini Pro ◄[/magenta]",
        "[bold cyan]╔════ UTIM REWARDS WHEEL ════╗[/bold cyan]\n    [yellow]► [4] Qwen 2.5 | [5] Gemini Pro | [6] Llama 3.3 ◄[/yellow]",
        "[bold cyan]╔════ UTIM REWARDS WHEEL ════╗[/bold cyan]\n    [cyan]► [5] Gemini Pro | [6] Llama 3.3 | [1] Claude 3.7 ◄[/cyan]"
    ]

    console.print("\n[bold gold1]Spinning the UTIM Rewards Wheel...[/bold gold1]\n")
    
    # Fast spin slowing down dynamically
    delays = [0.06] * 12 + [0.1] * 8 + [0.18] * 6 + [0.3] * 4 + [0.5] * 2
    
    with Live(console=console, refresh_per_second=20) as live:
        for idx, delay in enumerate(delays):
            frame = wheel_frames[idx % len(wheel_frames)]
            live.update(Panel(frame, border_style="gold1", title="[bold white]UTIM Wheel Spin[/bold white]"))
            time.sleep(delay)

        # Final winning landing panel
        cat_badge = {
            "free": "[bold green]FREE MODEL[/bold green]",
            "very_low": "[bold cyan]VERY LOW COST[/bold cyan]",
            "higher": "[bold yellow]HIGHER COST[/bold yellow]",
            "premium": "[bold magenta]⭐ PREMIUM JACKPOT ⭐[/bold magenta]"
        }.get(winning_category, "[bold white]REWARD[/bold white]")

        win_text = Text()
        win_text.append("SLOTS STOPPED! YOU WON:\n\n", style="bold gold1")
        win_text.append(f"{winning_name}\n", style="bold white underline")
        win_text.append(f"Category: {cat_badge}\n", style="italic")
        win_text.append("Duration: 24 Hours (Unlimited Usage without Quota Consumption)\n", style="bold green")

        live.update(Panel(win_text, border_style="green", title="[bold green]RESULT CONFIRMED[/bold green]"))
        time.sleep(0.5)


def run_rewards_cli_flow(console_out: Optional[Console] = None, spin_immediately: bool = False):
    """Main CLI entrypoint for /rewards slash command."""
    con = console_out or console
    if not console_out:
        con.clear()
    con.print(Panel("[bold cyan]UTIM REWARDS WHEEL HUB[/bold cyan]\nSpin the wheel to win 24-hour UNLIMITED access to top AI models!", border_style="cyan"))

    try:
        api_base = get_api_url()
        headers = get_auth_headers()
    except Exception as e:
        con.print(f"[bold red]Authentication Error:[/bold red] {e}")
        return

    try:
        status_data = _fetch_rewards_status(api_base, headers)
    except Exception as e:
        con.print(f"[bold red]Failed to load rewards status:[/bold red] {e}")
        return

    # Check paid plan status
    if not status_data.get("is_paid_plan"):
        con.print(Panel(
            "[bold red]Paid Plan Required[/bold red]\n\n"
            "The UTIM Rewards Wheel is available exclusively for paid subscribers.\n"
            "Upgrade your plan (Hobby ₹700, Pro ₹2,500, Max ₹5,500, Ultimate ₹11,000) to receive 4 spins every month!\n\n"
            "[yellow]Visit: https://utim.dev/upgrade[/yellow]",
            title="[bold red]Access Restricted[/bold red]",
            border_style="red"
        ))
        return

    # Render Spin Allowance HUD & Active Reward
    spins_left = status_data.get("spins_remaining", 0)
    spins_granted = status_data.get("spins_granted", 4)
    plan_display = status_data.get("plan_display_name", "Paid Plan")
    max_omits = status_data.get("max_omissions_allowed", 0)
    active_reward = status_data.get("active_reward")

    con.print(f"\n[bold white]Plan:[/bold white] [cyan]{plan_display}[/cyan] | [bold white]Monthly Spins Left:[/bold white] [bold green]{spins_left}/{spins_granted}[/bold green] | [bold white]Max Model Omissions Allowed:[/bold white] [yellow]{max_omits}[/yellow]")

    if active_reward:
        m_name = active_reward.get("model_name", active_reward.get("model_id"))
        rem_sec = active_reward.get("time_remaining_seconds", 0)
        hours = rem_sec // 3600
        mins = (rem_sec % 3600) // 60
        con.print(Panel(
            f"[bold green]ACTIVE 24-HOUR REWARD RUNNING:[/bold green] [bold white]{m_name}[/bold white]\n"
            f"Time Remaining: [bold yellow]{hours}h {mins}m[/bold yellow] (Requests to this model consume zero quota!)",
            border_style="green"
        ))

    # Omission Selector Flow
    current_omits = status_data.get("current_omissions", [])
    all_models = status_data.get("all_models", [])

    if max_omits > 0:
        con.print(f"\n[bold gold1]Model Omission Manager[/bold gold1] (Your plan allows omitting up to [yellow]{max_omits}[/yellow] models):")
        con.print("Currently omitted models: " + (", ".join(current_omits) if current_omits else "[italic dim]None[/italic dim]"))

    # Render Probability Table
    prob_data = status_data.get("probabilities", {})
    models_table = prob_data.get("models", [])
    
    table = Table(title="[bold white]Current Wheel Model Probabilities[/bold white]", border_style="dim")
    table.add_column("Model Name", style="bold white")
    table.add_column("Category", style="cyan")
    table.add_column("Probability", style="bold green", justify="right")

    for m in models_table:
        cat_badge = {"free": "[green]Free[/green]", "very_low": "[cyan]Very Low[/cyan]", "higher": "[yellow]Higher[/yellow]", "premium": "[magenta]Jackpot[/magenta]"}.get(m["category"], m["category"])
        table.add_row(clean_model_display_name(m.get("name"), m.get("model_id")), cat_badge, f"{m['probability_percent']:.4f}%")

    con.print("\n", table)

    if console_out is not None:
        con.print("\n[dim]Press UP/DOWN to scroll. Run /rewards spin in terminal to trigger an instant spin.[/dim]")
        return

    # Perform Spin Action if interactive
    if spins_left <= 0:
        con.print("\n[bold yellow]You have used all available spins for your current billing cycle.[/bold yellow]")
        return

    ready_spin = Confirm.ask("\n[bold gold1]Ready to spin the UTIM Rewards Wheel now?[/bold gold1]", default=True)
    if not ready_spin:
        con.print("[dim]Wheel spin cancelled. You can return anytime using /rewards.[/dim]")
        return

    # Trigger spin API
    try:
        spin_res = _perform_spin(api_base, headers)
        winning_model = spin_res["winning_model"]
        clean_win_name = clean_model_display_name(winning_model.get("name"), winning_model.get("model_id"))
        
        # Animate Wheel
        animate_terminal_wheel(clean_win_name, winning_model["category"])
        
        con.print(Panel(
            f"[bold green]SUCCESS![/bold green] You won 24-hour unlimited access to [bold white]{clean_win_name}[/bold white]!\n"
            f"Reward Active Until: [bold yellow]{spin_res.get('reward_end')}[/bold yellow]\n"
            f"Spins Remaining: [bold cyan]{spin_res.get('spins_remaining')}[/bold cyan]",
            border_style="green",
            title="[bold gold1]UTIM REWARD ACTIVATED[/bold gold1]"
        ))
    except Exception as e:
        con.print(f"\n[bold red]Spin Failed:[/bold red] {e}")
