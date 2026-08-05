import os
import json
import pathlib
import pytest
from unittest.mock import MagicMock, patch
from utim_cli.mcp_client import MCPManager
from utim_cli.orchestrator import Orchestrator, get_system_prompt
from rich.console import Console

def test_mcp_manager_caching_and_notification():
    manager = MCPManager()
    
    # Manually populate sessions and server_tools to simulate connection
    mock_session = MagicMock()
    manager.sessions["dummy_server"] = mock_session
    manager.server_tools["dummy_server"] = ["hello_tool", "goodbye_tool"]
    manager.cached_tools = [
        {
            "type": "function",
            "function": {
                "name": "dummy_server__hello_tool",
                "description": "[dummy_server] A hello tool",
                "parameters": {}
            }
        }
    ]
    
    assert manager.get_tools() == manager.cached_tools
    
    context = manager.get_notification_context()
    assert "this mcp server dummy_server is connected and a new set of tools are available for u: hello_tool, goodbye_tool" in context

def test_mcp_routing_and_display_arg():
    # Verify _get_display_arg displays arguments for MCP tools
    func_name = "dummy_server__hello_tool"
    arguments = {"name": "Alice", "age": 30}
    display = Orchestrator._get_display_arg(func_name, arguments)
    assert "name=Alice" in display
    assert "age=30" in display

@patch("utim_cli.mcp_client.mcp_manager")
def test_orchestrator_mcp_tool_execution(mock_mcp_manager):
    # Setup mock mcp_manager sessions and response
    mock_session = MagicMock()
    mock_mcp_manager.sessions = {"dummy_server": mock_session}
    mock_mcp_manager.call_tool.return_value = "Hello Alice!"
    
    console = Console()
    orchestrator = Orchestrator(console)
    
    tool_call = {
        "function": {
            "name": "dummy_server__hello_tool",
            "arguments": '{"name": "Alice"}'
        }
    }
    
    # Route tool execution
    result = orchestrator._execute_tool(tool_call)
    
    assert result == "Hello Alice!"
    mock_mcp_manager.call_tool.assert_called_once_with("dummy_server", "hello_tool", {"name": "Alice"})

@patch("utim_cli.mcp_client.mcp_manager")
def test_system_prompt_mcp_context(mock_mcp_manager):
    # Setup notification context
    mock_mcp_manager.get_notification_context.return_value = "this mcp server dummy_server is connected and a new set of tools are available for u: hello_tool"
    
    prompt = get_system_prompt()
    assert "### MCP SERVERS AND TOOLS NOTIFICATION ###" in prompt
    assert "this mcp server dummy_server is connected and a new set of tools are available for u: hello_tool" in prompt

def test_handle_mcp_command():
    from utim_cli.utim import _handle_command
    mock_app_ref = MagicMock()
    orchestrator = MagicMock()
    _handle_command("/mcp", orchestrator, mock_app_ref)
    mock_app_ref.exit.assert_called_once_with(result='mcp')

@patch("utim_cli.mcp_client.mcp_manager")
@patch("utim_cli.utim._run_list_dialog")
@patch("utim_cli.tui.mcp_dialog._dialog_mcp_install")
@patch("utim_cli.tui.mcp_dialog._dialog_mcp_manage")
@patch("utim_cli.utim.os.path.exists")
def test_dialog_mcp_flow(mock_exists, mock_manage, mock_install, mock_run_list_dialog, mock_mcp_manager):
    # Prevent test from loading user's local mcp.json
    mock_exists.return_value = False
    
    # Setup mock connected servers
    mock_mcp_manager.sessions = {"dummy_server": MagicMock()}
    mock_mcp_manager.server_tools = {"dummy_server": ["hello_tool"]}
    
    orchestrator = MagicMock()
    from utim_cli.utim import _dialog_mcp
    
    # Scenario 1: Select "Cancel" (index 1) -> should exit loop/dialog
    mock_run_list_dialog.return_value = ("select", 1)
    _dialog_mcp(orchestrator)
    mock_install.assert_not_called()
    mock_manage.assert_not_called()
    
    # Reset mocks
    mock_run_list_dialog.reset_mock()
    mock_install.reset_mock()
    mock_manage.reset_mock()
    
    # Scenario 2: Select "Install" (index 0), then "Cancel" (index 1) to break out of loop
    mock_run_list_dialog.side_effect = [("select", 0), ("select", 1)]
    _dialog_mcp(orchestrator)
    mock_install.assert_called_once_with(orchestrator)
    mock_manage.assert_not_called()
    
    # Reset mocks
    mock_run_list_dialog.reset_mock()
    mock_run_list_dialog.side_effect = None
    mock_install.reset_mock()
    mock_manage.reset_mock()
    
    # Scenario 3: Select a connected server "dummy_server" (index 2), then "Cancel" (index 1) to break loop
    mock_run_list_dialog.side_effect = [("select", 2), ("select", 1)]
    _dialog_mcp(orchestrator)
    mock_manage.assert_called_once_with(orchestrator, "dummy_server")
    mock_install.assert_not_called()

@patch("utim_cli.mcp_client.mcp_manager")
@patch("utim_cli.utim._run_mcp_search_list_dialog")
@patch("utim_cli.utim._prompt_input")
@patch("utim_cli.utim.os.path.exists")
@patch("builtins.open")
def test_dialog_mcp_install_preset(mock_open, mock_exists, mock_input, mock_run_dialog, mock_mcp_manager):
    with patch("utim_cli.utim.json.load") as mock_json_load:
        mock_json_load.return_value = {
            "sqlite": {
                "name": "SQLite Server",
                "desc": "SQLite database server",
                "pkg": "@modelcontextprotocol/server-sqlite",
                "fields": [
                    {"type": "arg", "key": "db_path", "prompt": "Enter db path: ", "required": True}
                ]
            }
        }
        # Select SQLite Server preset (index 0 because SQLite is the first element)
        mock_run_dialog.return_value = ("select", 0)
        
        # SQLite database path prompt value
        mock_input.return_value = "/path/to/test.db"
        mock_exists.return_value = False
        
        orchestrator = MagicMock()
        from utim_cli.utim import _dialog_mcp_install
        _dialog_mcp_install(orchestrator)
        
        # Verify manager restart was triggered
        mock_mcp_manager.restart.assert_called_once()


@patch("utim_cli.orchestrator.requests.post")
@patch("utim_cli.mcp_client.mcp_manager")
@patch("utim_cli.orchestrator.config.get")
def test_orchestrator_passes_mcp_tools_to_llm(mock_config_get, mock_mcp_manager, mock_post):
    mock_config_get.side_effect = lambda key, default=None: [] if key == "disabled_tools" else default
    # Setup mock MCP tools
    mock_mcp_manager.get_tools.return_value = [
        {
            "type": "function",
            "function": {
                "name": "dummy_server__hello_tool",
                "description": "A hello tool",
                "parameters": {}
            }
        }
    ]
    
    # Mock response for requests.post
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.encoding = "utf-8"
    
    # To mock the stream response of server-sent events
    mock_response.__enter__.return_value = mock_response
    mock_response.iter_lines.return_value = [
        'data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": "stop"}]}',
        'data: [DONE]'
    ]
    mock_post.return_value = mock_response
    
    console = Console()
    orchestrator = Orchestrator(console)
    orchestrator.model_id = "test-model"
    orchestrator._local_api_key = "test-key"
    
    orchestrator._call_llm([{"role": "user", "content": "hello"}], silent=True)
        
    mock_post.assert_called_once()
    kwargs = mock_post.call_args[1]
    payload = kwargs["json"]
    
    # Check that tools include both static UTIM_TOOLS and MCP tools
    tools = payload["tools"]
    tool_names = [t["function"]["name"] for t in tools]
    assert "read_file" in tool_names
    assert "dummy_server__hello_tool" in tool_names


@patch("utim_cli.utim.Application")
@patch("shutil.get_terminal_size")
def test_list_dialog_viewport_scrolling(mock_get_terminal_size, mock_application_class):
    # Mock terminal size to 15 lines
    mock_get_terminal_size.return_value = MagicMock(lines=15)
    
    content_fn = None
    def mock_run(*args, **kwargs):
        nonlocal content_fn
        layout = mock_application_class.call_args[1]["layout"]
        content_fn = layout.container.content.text
        
    dialog_app_instance = MagicMock()
    dialog_app_instance.run.side_effect = mock_run
    mock_application_class.return_value = dialog_app_instance
    
    rows = [{"name": f"Item {i}", "desc": "Desc"} for i in range(20)]
    def render_row(idx, row, selected):
        return [("", f"{row['name']}\n"), ("", "desc\n")]
        
    from utim_cli.utim import _run_list_dialog
    _run_list_dialog(rows, render_row, title="Test", legend="Legend")
    
    # Extract FormattedTextControl content callback and the keybindings
    kb2 = mock_application_class.call_args[1]["key_bindings"]
    down_bindings = kb2.get_bindings_for_keys(('down',))
    down_handler = down_bindings[0].handler
    
    # 1. Render initial viewport
    res_initial = content_fn()
    text_initial = "".join(part[1] for part in res_initial)
    assert "Item 0" in text_initial
    assert "Item 19" not in text_initial
    
    # 2. Scroll selection down 15 times
    mock_event = MagicMock()
    for _ in range(15):
        down_handler(mock_event)
        
    # 3. Render updated viewport
    res_scrolled = content_fn()
    text_scrolled = "".join(part[1] for part in res_scrolled)
    
    # The viewport should have scrolled: Item 15 visible, Item 0 scrolled out
    assert "Item 15" in text_scrolled
    assert "Item 0" not in text_scrolled


@patch("utim_cli.mcp_client.mcp_manager")
@patch("utim_cli.orchestrator.requests.post")
def test_orchestrator_call_llm_abort(mock_post, mock_mcp_manager):
    console = Console()
    orchestrator = Orchestrator(console)
    orchestrator.cancel_event.set()
    
    msg, was_streamed = orchestrator._call_llm([{"role": "user", "content": "hello"}], silent=True)
    
    assert msg.get("aborted") is True
    assert "[Aborted by user]" in msg.get("content")
    # Verify requests.post was never called because it aborted immediately
    mock_post.assert_not_called()


def test_tool_call_cleanup():
    from utim_cli.orchestrator import Orchestrator
    console = Console()
    orchestrator = Orchestrator(console)
    
    mock_read = MagicMock(return_value="File content")
    def dummy_read_file(filepath: str, start_line: int = None, end_line: int = None):
        return mock_read(filepath=filepath, start_line=start_line, end_line=end_line)
        
    from utim_cli import tools
    orig_get_tools = tools.get_tools
    
    def mock_get_tools():
        schemas, funcs = orig_get_tools()
        import copy
        funcs = copy.copy(funcs)
        funcs["read_file"] = dummy_read_file
        return schemas, funcs
        
    tools.get_tools = mock_get_tools
    
    try:
        # Corrupted XML representation inside function name
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "read_file filepath=\".utim/UTIM.md\" />",
                "arguments": "{}"
            }
        }
        
        # Execute the tool
        res = orchestrator._execute_tool(tool_call)
        
        # Verify it cleaned up the function name and parsed/extracted the attributes
        assert tool_call["function"]["name"] == "read_file"
        import json
        args = json.loads(tool_call["function"]["arguments"])
        assert args["filepath"] == ".utim/UTIM.md"
        mock_read.assert_called_once_with(filepath=".utim/UTIM.md", start_line=None, end_line=None)
        assert res == "File content"
    finally:
        tools.get_tools = orig_get_tools





