import json
import os
import re
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

# Global state management - using the existing STATE from utim_cli.state
class UTIMStateAdapter:
    def __init__(self):
        self._state_lock = threading.Lock()
    
    def add_hint_message(self, hint_text: str) -> None:
        """Add a hint message to the global state."""
        with self._state_lock:
            try:
                from utim_cli.state import STATE
                if "hint_messages" not in STATE:
                    STATE["hint_messages"] = []
                # Ensure it's a list and add the hint
                if isinstance(STATE["hint_messages"], list):
                    STATE["hint_messages"].append(hint_text)
                else:
                    # If it's not a list, replace with list
                    STATE["hint_messages"] = [hint_text]
            except Exception:
                # If import fails, silently handle for robustness
                pass
    
    def get_hint_messages(self) -> List[str]:
        """Get all hint messages from global state."""
        try:
            from utim_cli.state import STATE
            if "hint_messages" in STATE and isinstance(STATE["hint_messages"], list):
                return STATE["hint_messages"].copy()
        except Exception:
            pass
        return []
    
    def clear_hint_messages(self) -> None:
        """Clear all hint messages from global state."""
        with self._state_lock:
            try:
                from utim_cli.state import STATE
                if "hint_messages" in STATE and isinstance(STATE["hint_messages"], list):
                    STATE["hint_messages"] = []
            except Exception:
                pass

# Global state instance
state = UTIMStateAdapter()

# Helper method to mark hints as processed (using simple approach)
def mark_processed_hints(hints: List[str]):
    """Mark hints as processed in the global state.
    
    Args:
        hints: List of hint strings to mark as processed
    """
    # Since UTIMStateAdapter doesn't track processed state, 
    # we just remove them from the list by re-adding only unprocessed ones
    with state._state_lock:
        try:
            from utim_cli.state import STATE
            if "hint_messages" in STATE and isinstance(STATE["hint_messages"], list):
                # Keep only hints that weren't in the provided list
                remaining_hints = [h for h in STATE["hint_messages"] if h not in hints]
                STATE["hint_messages"] = remaining_hints
        except Exception:
            pass

def parse_hint_commands(content: str) -> Tuple[str, List[str]]:
    """Parse /hint commands from content and return cleaned content and extracted hints.
    
    Args:
        content: The input content to parse for /hint commands
        
    Returns:
        Tuple of (cleaned_content, list_of_hint_messages)
    """
    if not content:
        return content, []
    
    # Pattern to match <tool_call>/hint please be verbose I can't understand what you are doing</tool_call>
    hint_pattern = re.compile(r'<tool_call>/hint\s*(.*?)</tool_call>')
    
    hints = []
    cleaned_content = content
    
    for match in hint_pattern.finditer(content):
        hint_text = match.group(1).strip()
        if hint_text:
            hints.append(hint_text)
            # Remove the entire tool_call block from content
            cleaned_content = cleaned_content.replace(match.group(0), "")
    
    return cleaned_content.strip(), hints

def process_hint_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process hint messages in the conversation history.
    
    Args:
        messages: List of message dictionaries
        
    Returns:
        Updated list of messages with hints processed and added to system context
    """
    processed_messages = list(messages)
    new_messages = []
    
    for msg in processed_messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        # Check if this is a user message with a /hint command
        if role == "user" and isinstance(content, str):
            hint_text = None
            
            # Handle different /hint formats:
            # 1. "/hint please be verbose" 
            # 2. "<tool_call>/hint please be verbose</tool_call>"
            # 3. "/hint please be verbose" (as tool call)
            
            if content.startswith("/hint"):
                # Extract hint from /hint command
                hint_text = content[1:].strip()  # Remove leading '/' and space
                # Add hint to state
                state.add_hint_message(hint_text)
                # Keep original message but clean hint content
                new_content = "" if hint_text.startswith("/hint") else content
                new_messages.append({
                    "role": "user",
                    "content": new_content
                })
                
            else:
                # Check for /hint in tool calls
                tool_calls_match = re.search(r'<tool_call>/hint\s*(.*?)</tool_call>', content)
                if tool_calls_match:
                    hint_text = tool_calls_match.group(1).strip()
                    # Add hint to state
                    state.add_hint_message(hint_text)
                    # Clean up the tool call from content
                    cleaned_content = re.sub(r'<tool_call>/hint\s*.*?</tool_call>', "", content)
                    # Add cleaned content if anything remains
                    if cleaned_content.strip():
                        new_messages.append({
                            "role": "user",
                            "content": cleaned_content.strip()
                        })
                else:
                    new_messages.append(msg)
        else:
            new_messages.append(msg)
    
    return new_messages

def apply_hint_context(messages: List[Dict[str, Any]], system_prompt: str) -> str:
    """Apply hint context to system prompt for enhanced processing.
    
    Args:
        messages: List of conversation messages
        system_prompt: Original system prompt
        
    Returns:
        Enhanced system prompt with hint context
    """
    enhanced_prompt = system_prompt
    current_hints = state.get_hint_messages()
    
    if current_hints:
        hint_section = "\n\n# USER HINTS:\n"
        for i, hint in enumerate(current_hints, 1):
            hint_section += f"{i}. {hint}\n"
        hint_section += "\nPlease acknowledge and incorporate these hints in your response.\n"
        
        enhanced_prompt = enhanced_prompt + hint_section
        
        # Clear all hints after using them (one-time processing)
        state.clear_hint_messages()
    
    return enhanced_prompt