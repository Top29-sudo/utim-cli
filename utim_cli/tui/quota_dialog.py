def _dialog_quota(orchestrator):
    """Interactive TUI dialog to select the preferred credit quota (regular or bonus)."""
    from utim_cli.config import config
    from utim_cli.utim import console, _run_list_dialog

    current_pref = config.get("preferred_quota", "regular")

    options = [
        {"key": "regular", "name": "Regular Quota", "desc": "Uses your standard plan credit quota first (resets monthly)"},
        {"key": "bonus", "name": "Bonus Quota", "desc": "Uses your purchased/accrued bonus credits first (never expires)"}
    ]

    def render_row(i, row, sel):
        bg = 'bg:#006622 bold white' if sel else ''
        is_current = row["key"] == current_pref
        prefix = "➔ [Active] " if is_current else "   "

        # Color coding
        name_style = bg or 'bold #42bcf5' if row["key"] == "regular" else bg or 'bold #a6e3a1'

        return [
            (bg or 'white', prefix),
            (name_style, f"{row['name']}\n"),
            (bg or 'class:dim', f"   {row['desc']}\n")
        ]

    action, idx = _run_list_dialog(
        options, render_row,
        title="Select Preferred Credit Quota",
        legend="↑↓ Navigate  Enter Select  q/Esc Cancel"
    )

    if action == 'select':
        selected = options[idx]["key"]
        config.set("preferred_quota", selected)
        console.print(f"\n  [bold green]✓ Preferred quota updated:[/bold green] Prioritizing [bold white]{selected}[/bold white] quota first.\n")
