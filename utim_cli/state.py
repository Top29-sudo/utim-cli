# Global App State
STATE = {
    "mode": "auto-accept edits",
    "busy": False,
    "busy_start": None,
    "session_id": None,
    "last_ctrl_c": 0.0,   # timestamp of the last Ctrl+C press
    "focused_process": None,  # process_id when user is focused on a background process
    "focus_mode": False,      # True when user is in terminal focus mode
    "queue": [],              # queue for prompts
    "planning_mode": False,    # True = wait for approval, False = Autonomous
    "tool_view": {"active": False, "index": -1}, # Inspector mode
    "tools_expanded": False,    # Toggle global tool results inline expand/collapse
    "thinking_topic": "",     # Dynamic topic for the spinner
    "is_verified": False,     # True if user has entered the secret code in this session
}
