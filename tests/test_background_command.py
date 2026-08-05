import time
import pytest
import sys
from utim_cli.tools import (
    run_command,
    list_background_processes,
    get_background_output,
    send_background_input,
    stop_background_process,
    shell_send_to_background,
    _BACKGROUND_PROCESSES,
)

def test_run_command_background_execution():
    # Run a long sleeping command in background mode with wait_seconds=1
    cmd = 'python -c "import time; print(\'Server started\'); time.sleep(10)"'
    res = run_command(command=cmd, is_background=True, wait_seconds=1)
    
    assert "[Command running in background:" in res
    assert "Server started" in res
    
    # Check process in listing
    listing = list_background_processes()
    assert "bg-" in listing
    assert "Running" in listing
    
    # Extract background ID
    bg_id = list(_BACKGROUND_PROCESSES.keys())[-1]
    
    # Fetch output
    out = get_background_output(bg_id)
    assert "Server started" in out
    assert "Running" in out
    
    # Stop background process
    stop_res = stop_background_process(bg_id)
    assert "terminated" in stop_res or "already terminated" in stop_res
    
    time.sleep(0.5)
    post_out = get_background_output(bg_id)
    assert "Exited" in post_out

def test_interactive_detach_to_background():
    # Trigger background detach signal
    cmd = 'python -c "import time; print(\'Long running script\'); time.sleep(10)"'
    
    shell_send_to_background()
    res = run_command(command=cmd)
    
    assert "[Command detached to background:" in res
    assert "Long running script" in res
    
    bg_id = list(_BACKGROUND_PROCESSES.keys())[-1]
    stop_res = stop_background_process(bg_id)
    assert "terminated" in stop_res or "already terminated" in stop_res
