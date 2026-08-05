def _dialog_rewind(orchestrator):
    history = orchestrator.turn_history
    if not history:
        console.print("\n[dim yellow]No turns to rewind.[/dim yellow]\n")
        return

    rows = list(history) + [None]  # None = "stay here" sentinel

    def render_turn(i, row, sel):
        bg = 'bg:#006622 bold white' if sel else ''
        if row is None:
            return [
                (bg or 'bold #42bcf5', '  \u25cf Stay at current position\n'),
                (bg or 'dim',          '  Cancel rewind and stay here\n'),
            ]
        msg  = row['user_msg'][:80] + ('\u2026' if len(row['user_msg']) > 80 else '')
        stat = orchestrator._change_stats(row['changes'])
        turn_num = i + 1
        return [
            (bg or 'white', f'  {turn_num}. {msg}\n'),
            (bg or 'dim',   f'     {stat}\n'),
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
        bg = 'bg:#006622 bold white' if sel else ''
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
    
    # Clear the screen so old chat output is gone — then replay remaining context
    console.clear()

    parts = ['[bold #a6e3a1]\u2713 Rewind complete.[/bold #a6e3a1]']
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
    history = orchestrator.turn_history
    if not history:
        console.print("\n[dim yellow]No active turns to undo.[/dim yellow]\n")
        return

    rows = list(history) + [None]  # None = cancel

    def render_turn(i, row, sel):
        bg = 'bg:#800000 bold white' if sel else ''  # Red accent for undo
        if row is None:
            return [
                (bg or 'bold #42bcf5', '  ● Keep everything (Cancel)\n'),
                (bg or 'dim',          '    Exit dialog and make no changes\n'),
            ]
        msg  = row['user_msg'][:80] + ('\u2026' if len(row['user_msg']) > 80 else '')
        stat = orchestrator._change_stats(row['changes'])
        turn_num = i + 1
        return [
            (bg or 'white', f'  {turn_num}. {msg}\n'),
            (bg or 'dim',   f'     {stat}\n'),
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
    
    console.clear()
    parts = [f'[bold #a6e3a1]\u2713 Undo complete ({n_reverted} turn(s) reverted).[/bold #a6e3a1]']
    if res.get('reverted'):
        parts.append(f"  [dim]Reverted: {', '.join(res['reverted'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))
    
    # Reprint remaining conversation history
    remaining = orchestrator.messages
    if remaining:
        turns = [
            (m['role'], m.get('content') or '')
            for m in remaining
            if m.get('role') in ('user', 'assistant') and m.get('content')
        ]
        if turns:
            from rich.rule import Rule
            from rich.markdown import Markdown
            w = min(console.size.width - 4, 100)
            console.print()
            console.print(Rule('[dim #42bcf5] ↶  Conversation after undo [/dim #42bcf5]', style='dim #42bcf5'))
            console.print()
            for role, content in turns:
                if role == 'user':
                    preview = content.strip()[:220] + ('\u2026' if len(content.strip()) > 220 else '')
                    console.print(f'[bold #42bcf5]❯[/bold #42bcf5] {preview}')
                else:
                    preview = content.strip()[:500] + ('\u2026' if len(content.strip()) > 500 else '')
                    console.print(Markdown(preview), width=w)
                console.print()
            console.print(Rule('[dim]Continue below[/dim]', style='dim'))
    console.print()


def _dialog_redo(orchestrator):
    redo_hist = getattr(orchestrator, "redo_history", [])
    if not redo_hist:
        console.print("\n[dim yellow]No undone turns to redo.[/dim yellow]\n")
        return

    rows = list(redo_hist) + [None]

    def render_turn(i, row, sel):
        bg = 'bg:#006622 bold white' if sel else ''  # Green accent for redo
        if row is None:
            return [
                (bg or 'bold #42bcf5', '  ● Keep current state (Cancel)\n'),
                (bg or 'dim',          '    Exit dialog and make no changes\n'),
            ]
        msg  = row['user_msg'][:80] + ('\u2026' if len(row['user_msg']) > 80 else '')
        stat = orchestrator._change_stats(row['changes'])
        turn_num = i + 1
        return [
            (bg or 'white', f'  {turn_num}. {msg}\n'),
            (bg or 'dim',   f'     {stat}\n'),
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
    
    console.clear()
    parts = [f'[bold #a6e3a1]\u2713 Redo complete ({n_redone} turn(s) redone).[/bold #a6e3a1]']
    if res.get('redone_code'):
        parts.append(f"  [dim]Redone: {', '.join(res['redone_code'][:5])}[/dim]")
    if res.get('errors'):
        parts.append(f"  [red]Errors: {'; '.join(res['errors'])}[/red]")
    console.print('\n'.join(parts))
    
    # Reprint remaining conversation history
    remaining = orchestrator.messages
    if remaining:
        turns = [
            (m['role'], m.get('content') or '')
            for m in remaining
            if m.get('role') in ('user', 'assistant') and m.get('content')
        ]
        if turns:
            from rich.rule import Rule
            from rich.markdown import Markdown
            w = min(console.size.width - 4, 100)
            console.print()
            console.print(Rule('[dim #42bcf5] ↷  Conversation after redo [/dim #42bcf5]', style='dim #42bcf5'))
            console.print()
            for role, content in turns:
                if role == 'user':
                    preview = content.strip()[:220] + ('\u2026' if len(content.strip()) > 220 else '')
                    console.print(f'[bold #42bcf5]❯[/bold #42bcf5] {preview}')
                else:
                    preview = content.strip()[:500] + ('\u2026' if len(content.strip()) > 500 else '')
                    console.print(Markdown(preview), width=w)
                console.print()
            console.print(Rule('[dim]Continue below[/dim]', style='dim'))
    console.print()


