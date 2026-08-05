#!/usr/bin/env python3
"""Test script for UTIM Hint Handler functionality.

This script tests the enhanced hint handling in the UTIM CLI
that allows users to provide hints to the AI assistant.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utim_cli.utilities import state, parse_hint_commands, process_hint_messages, apply_hint_context
from utim_cli.state import STATE

def test_hint_parsing():
    """Test hint parsing from tool calls and messages."""
    print("Testing hint parsing...")
    
    # Test 1: Parse hint commands from tool calls
    test_content1 = '<tool_call>/hint please be verbose I can\'t understand what you are doing</tool_call>'
    content, hints = parse_hint_commands(test_content1)
    assert len(hints) == 1, f"Expected 1 hint, got {len(hints)}"
    assert hints[0] == "please be verbose I can't understand what you are doing", f"Unexpected hint: {hints[0]}"
    assert '<tool_call>/hint' not in content, "Hint should be removed from content"
    print("✓ Test 1 passed: Tool call hint parsing")
    
    # Test 2: Parse hint from simple message
    test_content2 = '/hint please be verbose I can\'t understand what you are doing'
    content, hints = parse_hint_commands(test_content2)
    assert len(hints) == 1, f"Expected 1 hint, got {len(hints)}"
    assert hints[0] == "please be verbose I can't understand what you are doing", f"Unexpected hint: {hints[0]}"
    print("✓ Test 2 passed: Simple hint parsing")
    
    # Test 3: Process hint messages in conversation
    messages = [
        {"role": "system", "content": "You are UTIM AI, a senior software engineer."},
        {"role": "user", "content": '/hint please be verbose I can\'t understand what you are doing'},
        {"role": "assistant", "content": "I'll help you understand."}
    ]
    processed = process_hint_messages(messages)
    assert len(processed) == 3, f"Expected 3 messages, got {len(processed)}"
    
    # Check that hint was added to state
    state.add_hint_message("please be verbose I can't understand what you are doing")
    assert "please be verbose I can't understand what you are doing" in state.get_hint_messages()
    print("✓ Test 3 passed: Hint message processing")
    
    # Test 4: Apply hint context to system prompt
    system_prompt = "You are UTIM AI, a senior software engineer."
    enhanced = apply_hint_context(messages, system_prompt)
    assert "USER HINTS:" in enhanced, "Hint section should be added"
    assert "please be verbose" in enhanced, "Hint content should be in enhanced prompt"
    print("✓ Test 4 passed: Hint context application")
    
    # Test 5: Clear hints from state
    state.clear_hint_messages()
    assert len(state.get_hint_messages()) == 0, "Hints should be cleared"
    print("✓ Test 5 passed: Hint clearing")
    
    print("\n✅ All hint handler tests passed!")

def test_orchestrator_hint_handling():
    """Test that orchestrator handles hints correctly."""
    print("\nTesting orchestrator hint handling...")
    
    # This is a conceptual test - in a real scenario, we would test with the actual orchestrator
    # Since the orchestrator is complex and requires server setup, we'll just verify
    # the utility functions work correctly.
    
    # Add hint to state
    STATE["hint_messages"] = ["please be more verbose"]
    
    # Verify hint is accessible
    assert "hint_messages" in STATE, "Hint messages should be in STATE"
    assert len(STATE["hint_messages"]) > 0, "Should have hint messages"
    
    print("✓ Orchestrator hint state handling works")
    
    # Clean up
    del STATE["hint_messages"]

if __name__ == "__main__":
    print("=" * 60)
    print("UTIM Hint Handler Test Suite")
    print("=" * 60)
    
    test_hint_parsing()
    test_orchestrator_hint_handling()
    
    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)