"""
UTIM Rewards Wheel CLI Module
──────────────────────────────
Dedicated module for Rewards Wheel CLI commands, completion metadata,
and interactive terminal execution.
"""

from typing import Dict, Any, List

# Wheel slash commands metadata
WHEEL_COMMANDS: Dict[str, str] = {
    "rewards": "Spin the UTIM Rewards Wheel for 24-hour unlimited model access",
}

def is_wheel_command(cmd_name: str) -> bool:
    """Check if command name is a rewards wheel command."""
    if not cmd_name:
        return False
    clean = cmd_name.lstrip("/").lower().strip()
    return clean == "rewards"

def execute_wheel_cli_flow():
    """Delegate execution to the Rewards TUI flow."""
    from .tui.rewards_tui import run_rewards_cli_flow
    run_rewards_cli_flow()
