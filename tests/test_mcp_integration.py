import os
import json
import sys
import pathlib
import time
import pytest
from utim_cli.mcp_client import MCPManager

def test_real_mcp_connection_integration():
    mcp_dir = pathlib.Path(".utim").resolve()
    mcp_config_file = mcp_dir / "mcp.json"
    
    # 1. Backup existing config
    backup_data = None
    existed = mcp_config_file.exists()
    if existed:
        try:
            with open(mcp_config_file, "r") as f:
                backup_data = json.load(f)
        except Exception:
            pass
            
    # Locate dummy server path
    dummy_server_path = os.path.abspath(
        os.path.join(
            "C:\\Users\\user\\.gemini\\antigravity-cli\\brain\\ad1038f4-b10f-4de1-84e4-c7928bda052a",
            "scratch",
            "dummy_mcp_server.py"
        )
    )
    
    # Write mock config pointing to our dummy server script
    mcp_config = {
        "mcpServers": {
            "dummy_integration": {
                "command": sys.executable,
                "args": [dummy_server_path]
            }
        }
    }
    
    mcp_dir.mkdir(parents=True, exist_ok=True)
    with open(mcp_config_file, "w") as f:
        json.dump(mcp_config, f, indent=2)
        
    try:
        # Create a fresh manager instance
        manager = MCPManager()
        
        # Start manager
        manager.start()
        
        # Verify dummy_integration is connected
        assert "dummy_integration" in manager.sessions
        
        # Verify tools are loaded
        tools = manager.get_tools()
        assert len(tools) > 0
        assert tools[0]["function"]["name"] == "dummy_integration__echo"
        
        # Verify notification context
        context = manager.get_notification_context()
        assert "this mcp server dummy_integration is connected and a new set of tools are available for u: echo" in context
        
        # Verify tool call execution
        res = manager.call_tool("dummy_integration", "echo", {"message": "Hello from Integration Test!"})
        assert "Echo: Hello from Integration Test!" in res
        
    finally:
        # Restore backup or cleanup
        if existed and backup_data is not None:
            with open(mcp_config_file, "w") as f:
                json.dump(backup_data, f, indent=2)
        elif mcp_config_file.exists():
            try:
                mcp_config_file.unlink()
            except Exception:
                pass
