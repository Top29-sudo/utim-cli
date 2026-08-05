import pytest
from unittest.mock import MagicMock
from rich.console import Console
from utim_cli.utim import _handle_command, STATE
from utim_cli.orchestrator import Orchestrator

def test_hint_command_and_injection():
    # Reset hint state
    STATE["hint"] = None
    
    console = Console()
    orchestrator = Orchestrator(console)
    app_ref = MagicMock()
    
    # 1. Test running /hint with no arguments
    _handle_command("/hint", orchestrator, app_ref)
    assert STATE.get("hint") is None
    
    # 2. Test running /hint with valid content
    _handle_command("/hint speak in french please", orchestrator, app_ref)
    assert STATE.get("hint") == "speak in french please"
    
    # 3. Verify hint is injected into the next run_task message
    # Mock self._get_send_messages and completions to avoid actual network/LLM requests
    orchestrator.messages = []
    orchestrator._persist_messages = MagicMock()
    
    # We patch or intercept the loop so we don't hit the real completions endpoint
    orig_call_llm = orchestrator._call_llm
    orchestrator._call_llm = MagicMock(return_value=({"content": "Mocked answer", "tool_calls": []}, False))
    
    try:
        # Run orchestrator task with a dummy task, let it break early or finish first turn
        orchestrator.run_task("Hello", max_iterations=1)
        
        # Verify the user message appended contains the hint prefix
        user_message_in_history = orchestrator.messages[0]
        assert user_message_in_history["role"] == "user"
        assert "[Secret Hint Guidance: speak in french please]" in user_message_in_history["content"]
        assert "Hello" in user_message_in_history["content"]
        
        # Verify the hint state is cleared after injection
        assert STATE.get("hint") is None
    finally:
        orchestrator._call_llm = orig_call_llm
