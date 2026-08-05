from utim_cli.local_db import HistoryManager, _make_session, _parse_json_field, Conversation
from utim_cli.state import STATE
import datetime

def _dialog_resume(orchestrator):
    # Import UI dependencies locally to avoid circular import with utim.py
    from utim_cli.utim import console, _run_list_dialog

    hm = HistoryManager()
    sessions = hm.list_sessions()
    
    if not sessions:
        console.print("\n[dim]No saved conversations found. Start chatting and your history will be saved automatically.[/dim]\n")
        return

    def _age(ts):
        try:
            dt = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
            delta = datetime.datetime.now(datetime.timezone.utc) - dt
            mins = int(delta.total_seconds() // 60)
            if mins < 60:
                return f"{mins}m"
            h = mins // 60
            return f"{h}h" if h < 24 else f"{h // 24}d"
        except Exception:
            return "?"

    def _extract_text(content) -> str:
        """Safely extract string from a message content field (may be str or list of parts)."""
        if isinstance(content, list):
            return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        return str(content or "")

    def render_sess(i, s, sel):
        bg      = 'bg:#1a3a2a bold #cdd6f4' if sel else ''
        hi      = 'bold #42bcf5' if sel else 'class:dim fg:#585b70'
        msgs    = s.get('message_count', 0)
        age     = _age(s.get('updated_at', s.get('created_at', '')))
        # Title is the first user prompt (server already derives this)
        title   = s.get('title') or '(no messages)'
        # Build a human-readable date from updated_at so same-title sessions are
        # distinguishable (e.g. two runs of the same prompt on different days).
        try:
            dt_raw = s.get('updated_at') or s.get('created_at') or ''
            dt = datetime.datetime.fromisoformat(dt_raw.replace('Z', '+00:00'))
            # Show local-ish date+time (strip timezone for brevity)
            date_str = dt.strftime('%b %d  %H:%M')
        except Exception:
            date_str = ''
        # Trim title to fit terminal — leave room for date + msg count suffix
        max_w   = max(20, (console.size.width or 100) - 26)
        if len(title) > max_w:
            title = title[:max_w - 1] + '…'
        age_str  = f'[{age}]'
        msg_str  = f'{msgs} msgs'
        date_tag = f'  {date_str}' if date_str else ''
        return [
            (bg or 'bold #cdd6f4', f'  {title}\n'),
            (bg or hi,             f'    {age_str}  {msg_str}{date_tag}\n'),
        ]

    action, idx = _run_list_dialog(
        sessions, render_sess,
        title=f'↩  Resume conversation  ({len(sessions)} saved)',
        legend='↑↓ Navigate   Enter Select   q/Esc Cancel',
    )
    if action != 'select':
        return

    sid     = sessions[idx]['session_id']
    s_title = sessions[idx].get('title', sid[:12])

    # Load full message history from local database
    try:
        db = _make_session()
        conv = db.query(Conversation).filter(Conversation.id == sid).first()
        if not conv:
            console.print(f"\n[red]Conversation not found in local database.[/red]\n")
            db.close()
            return
        
        server_msgs = _parse_json_field(conv.messages)
        model_id = conv.model_id or orchestrator.model_id
        db.close()
    except Exception as e:
        console.print(f"\n[red]Failed to load conversation: {e}[/red]\n")
        return

    if not conv:
        console.print(f"\n[red]Conversation not found in local database.[/red]\n")
        return

    if not server_msgs:
        console.print("\n[dim yellow]That conversation has no saved messages.[/dim yellow]\n")
        return

    # Ensure the system prompt is present as message[0]
    has_system = any(m.get('role') == 'system' for m in server_msgs)
    if not has_system:
        from utim_cli.orchestrator import get_system_prompt
        server_msgs = [{"role": "system", "content": get_system_prompt()}] + server_msgs

    # Restore orchestrator full state
    orchestrator.session_id     = sid
    orchestrator.model_id       = model_id
    orchestrator.messages       = server_msgs
    orchestrator._turn_changes  = []
    STATE['session_id']         = sid

    if hasattr(conv, "turn_history") and conv.turn_history:
        orchestrator.turn_history = _parse_json_field(conv.turn_history)
        orchestrator.redo_history = _parse_json_field(conv.redo_history)
    else:
        # Reconstruct turn_history from the message list so /rewind still works.
        # Each user message starts a new turn; we group: user + assistant (+tool*) messages.
        orchestrator.turn_history = []
        orchestrator.redo_history = []
        i = 0
        while i < len(server_msgs):
            m = server_msgs[i]
            c_text = _extract_text(m.get('content', ''))
            if m.get('role') == 'user' and not ("### SYSTEM NOTE:" in c_text or "[System Note:" in c_text or "Context Stabilization Summary" in c_text):
                turn_start = i
                user_text  = c_text
                i += 1
                # Consume the assistant reply and any tool call / tool result messages
                while i < len(server_msgs) and server_msgs[i].get('role') in ('assistant', 'tool'):
                    i += 1
                orchestrator.turn_history.append({
                    'user_msg':  user_text,
                    'msg_start': turn_start,
                    'msg_end':   i,
                    'messages':  list(server_msgs[turn_start:i]),
                    'changes':   [],  # we can't recover file changes from cloud/old history
                })
            else:
                i += 1

    # Derive topic for display
    topic = s_title or next(
        (_extract_text(m.get('content', '')) for m in server_msgs if m.get('role') == 'user'),
        sid[:12],
    )
    STATE['session_topic'] = topic

    # Return messages so start_chat can display them
    return server_msgs
