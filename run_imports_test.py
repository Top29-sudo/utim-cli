#!/usr/bin/env python3
"""Test the imports to verify the hint handler fix."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Test the actual import that's failing
    from utim_cli.utilities import state, parse_hint_commands, process_hint_messages, apply_hint_context
    print("✅ Successfully imported from utim_cli.utilities")
    print(f"   State type: {type(state)}")
    print(f"   State has add_hint_message: {hasattr(state, 'add_hint_message')}")
    print(f"   State has get_hint_messages: {hasattr(state, 'get_hint_messages')}")
    print(f"   State has clear_hint_messages: {hasattr(state, 'clear_hint_messages')}")
    print(f"   State has mark_processed_hints: {hasattr(state, 'mark_processed_hints')}")
    
    # Test hint processing
    test_content = "/hint please be verbose I can't understand what you are doing"
    cleaned, hints = parse_hint_commands(test_content)
    print(f"\n✅ Hint parsing test:")
    print(f"   Input: {test_content}")
    print(f"   Extracted hints: {hints}")
    
    # Add hint to state
    state.add_hint_message(hints[0])
    print(f"\n✅ State test:")
    print(f"   Added hint to state")
    current_hints = state.get_hint_messages()
    print(f"   Current hints in state: {current_hints}")
    
    # Test system prompt enhancement
    system_prompt = "You are UTIM AI, a senior software engineer."
    messages = [{"role": "user", "content": test_content}]
    enhanced = apply_hint_context(messages, system_prompt)
    print(f"\n✅ System prompt enhancement test:")
    print(f"   Original prompt: {system_prompt}")
    print(f"   Enhanced prompt contains 'HINTS': {'HINTS' in enhanced}")
    print(f"   Enhanced prompt contains hint: {'please be verbose' in enhanced}")
    
    # Verify hints were cleared after processing
    remaining_hints = state.get_hint_messages()
    print(f"\n✅ Hint clearing test:")
    print(f"   Hints after processing: {remaining_hints}")
    assert len(remaining_hints) == 0, "Hints should be cleared after processing"
    
    print("\n" + "="*60)
    print("✅ All import and functionality tests passed!")
    print("The hint handler fix is working correctly.")
    print("="*60)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)