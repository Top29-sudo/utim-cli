import json
import time

def _dialog_rewind(orchestrator):
    from utim_cli.utim import console, _run_list_dialog, _clear_terminal_screen, _print_session_history
    history = orchestrator.turn_history
    if not history:
        console.print("\n[dim yellow]No turns to rewind.[/dim yellow]\n")
        return

    rows = list(history) + [None]  # None = "stay here" sentinel

    def render_turn(i, row, sel):
        bg = 'bg:#313244 fg:#ffffff bold' if sel else ''
        if row is None:
            return [
                (bg or 'bold white', '  \u25cf Stay at current position\n'),
                (bg or 'class:dim',          '  Cancel rewind and stay here\n'),
            ]
        user_text = row.get('user_msg', '')
        if "### SYSTEM NOTE:" in user_text or "[System Note:" in user_text or "Context Stabilization Summary" in user_text:
            # Fallback to finding real prompt inside turn messages
            real_msg = next((m.get("content", "") for m in row.get("messages", []) if m.get("role") == "user" and "### SYSTEM NOTE:" not in str(m.get("content", ""))), "")
            user_text = str(real_msg) if real_msg else "User Task"
        msg  = user_text[:80] + ('\u2026' if len(user_text) > 80 else '')
        stat = orchestrator._change_stats(row['changes'])
        turn_num = i + 1
        return [
            (bg or 'white', f'  {turn_num}. {msg}\n'),
            (bg or 'class:dim',   f'     {stat}\n'),
        ]

    action, idx = _run_list_dialog(
        rows, render_turn,
        title=f'> Rewind  ({len(history)} turns)',
        legend='\u2191\u2193 Navigate  Enter Select  q Quit',
    )
    if action != 'select' or rows[idx] is None:
        return

    turn_idx = idx
    turn     = history[turn_idx]
    n_files  = len({c['path'] for c in turn['changes']})
    stat     = orchestrator._change_stats(turn['changes'])
    turn_num = turn_idx + 1

    options = [
        ('this_both', f'1. Rewind turn #{turn_num} (conversation + code changes)'),
        ('this_msgs', f'2. Rewind turn #{turn_num} conversation only'),
        ('this_code', f'3. Revert turn #{turn_num} code changes only'),
        ('from_both', f'4. Rewind from turn #{turn_num} onward (all changes)'),
        ('none', '5. Cancel (esc)'),
    ]

    def render_opt(i, row, sel):
        bg = 'bg:#313244 fg:#ffffff bold' if sel else ''
        return [(bg or 'white', f'  {row[1]}\n')]

    action2, idx2 = _run_list_dialog(
        options, render_opt,
        title='Confirm Rewind',
        legend=f'  Turn #{turn_num}: {n_files} file(s) affected   {stat}\n  Enter to confirm  q/Esc to cancel',
    )
    if action2 != 'select':
        return

    choice = options[idx2][0]
    if choice == 'none':
        return

    # Determine if we're rewinding just this turn or from this turn onward
    if choice.startswith('this_'):
        # Rewind only the selected turn
        revert_type = choice.replace('this_', '')
        res = orchestrator.rewind_single_turn(
            turn_idx,
            revert_code=(revert_type in ('both', 'code')),
            revert_msgs=(revert_type in ('both', 'msgs')),
        )
    else:
        # Rewind from this turn onward (old behavior)
        revert_type = choice.replace('from_', '')
        res = orchestrator.rewind_to_turn(
            turn_idx,
            revert_code=(revert_type in ('both', 'code')),
            revert_msgs=(revert_type in ('both', 'msgs')),
        )
    
    # Clear the screen so old chat output is gone — then replay banner and remaining context
    from utim_cli.utim import _print_animated_banner
    _clear_terminal_screen()
    _print_animated_banner(animated=False)

    parts = ['[bold white]✓ Rewind complete.[/bold white]']
    if res.get('reverted'):
        parts.append(f"  [dim]Reverted: {', '.join(res['reverted'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))

    # Reprint whatever conversation remains after the rewind
    remaining = orchestrator.messages
    if remaining:
        _print_session_history(orchestrator, remaining, 'Conversation after rewind')


def _dialog_undo(orchestrator):
    from utim_cli.utim import console, _transient_status, _clear_terminal_screen, _run_list_dialog, _print_animated_banner, _print_session_history
    history = orchestrator.turn_history
    if not history:
        console.print("\n[dim yellow]No active turns to undo.[/dim yellow]\n")
        return

    rows = list(history) + [None]  # None = cancel

    def render_turn(i, row, sel):
        bg = 'bg:#313244 fg:#ffffff bold' if sel else ''  # Red accent for undo
        if row is None:
            return [
                (bg or 'bold white', '  ● Keep everything (Cancel)\n'),
                (bg or 'class:dim',          '    Exit dialog and make no changes\n'),
            ]
        msg  = row['user_msg'][:80] + ('…' if len(row['user_msg']) > 80 else '')
        stat = orchestrator._change_stats(row['changes'])
        turn_num = i + 1
        return [
            (bg or 'white', f'  {turn_num}. {msg}\n'),
            (bg or 'class:dim',   f'     {stat}\n'),
        ]

    action, idx = _run_list_dialog(
        rows, render_turn,
        title=f'↶  Undo up to previous prompts  ({len(history)} active turns)',
        legend='↑↓ Navigate   Enter to Undo from selected turn onward   q/Esc Cancel',
    )
    if action != 'select' or rows[idx] is None:
        return

    n_reverted = len(history) - idx
    console.print(f"\n[dim]⌛ Undoing turns from #{idx+1} onward...[/dim]")
    res = orchestrator.rewind_to_turn(idx, revert_code=True, revert_msgs=True)
    orchestrator._persist_messages()
    
    _clear_terminal_screen()
    _print_animated_banner(animated=False)

    parts = [f'[bold white]✓ Undo complete ({n_reverted} turn(s) reverted).[/bold white]']
    if res.get('reverted'):
        parts.append(f"  [dim]Reverted: {', '.join(res['reverted'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))
    
    # Reprint remaining conversation history with full tool indicators
    remaining = orchestrator.messages
    if remaining:
        _print_session_history(orchestrator, remaining, 'Conversation after undo')


def _dialog_redo(orchestrator):
    from utim_cli.utim import console, _transient_status, _run_list_dialog, _clear_terminal_screen, _print_animated_banner, _print_session_history
    redo_hist = getattr(orchestrator, "redo_history", [])
    if not redo_hist:
        console.print("\n[dim yellow]No undone turns to redo.[/dim yellow]\n")
        return

    rows = list(redo_hist) + [None]

    def render_turn(i, row, sel):
        bg = 'bg:#313244 fg:#ffffff bold' if sel else ''  # Green accent for redo
        if row is None:
            return [
                (bg or 'bold white', '  ● Keep current state (Cancel)\n'),
                (bg or 'class:dim',          '    Exit dialog and make no changes\n'),
            ]
        msg  = row['user_msg'][:80] + ('…' if len(row['user_msg']) > 80 else '')
        stat = orchestrator._change_stats(row['changes'])
        turn_num = i + 1
        return [
            (bg or 'white', f'  {turn_num}. {msg}\n'),
            (bg or 'class:dim',   f'     {stat}\n'),
        ]

    action, idx = _run_list_dialog(
        rows, render_turn,
        title=f'↷  Redo previously undone prompts  ({len(redo_hist)} undone turns)',
        legend='↑↓ Navigate   Enter to Redo up to selected turn   q/Esc Cancel',
    )
    if action != 'select' or rows[idx] is None:
        return

    n_redone = idx + 1
    console.print(f"\n[dim]⌛ Redoing turns up to #{idx+1}...[/dim]")
    res = orchestrator.redo_up_to_turn(idx)
    
    _clear_terminal_screen()
    _print_animated_banner(animated=False)

    parts = [f'[bold white]✓ Redo complete ({n_redone} turn(s) redone).[/bold white]']
    if res.get('redone_code'):
        parts.append(f"  [dim]Redone: {', '.join(res['redone_code'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))
    
    # Reprint remaining conversation history with full tool indicators
    remaining = orchestrator.messages
    if remaining:
        _print_session_history(orchestrator, remaining, 'Conversation after redo')


