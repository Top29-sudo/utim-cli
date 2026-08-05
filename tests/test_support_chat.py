import json
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from utim_cli.server.router import app, server_execute_tool, parse_xml_tool_calls

def test_parse_xml_tool_calls():
    raw = "Let me check: <tool_call>\nread_page_docs\n<arg_key>page_name</arg_key>\n<arg_value>pricing</arg_value>\n</tool_call>"
    calls = parse_xml_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0]["name"] == "read_page_docs"
    assert calls[0]["arguments"] == {"page_name": "pricing"}


def test_server_execute_tool(tmp_path):
    # Test reading existing page
    docs_dir = tmp_path / "landing" / "src" / "docs_md"
    docs_dir.mkdir(parents=True)
    pricing_file = docs_dir / "pricing.md"
    pricing_file.write_text("Pricing info: $10/mo", encoding="utf-8")

    from unittest.mock import mock_open
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data="Pricing info: $10/mo")):
        res = server_execute_tool("read_page_docs", {"page_name": "pricing"})
        assert "Pricing info: $10/mo" in res

    # Test navigate_to_page
    res = server_execute_tool("navigate_to_page", {"page_path": "/features"})
    assert "Successfully navigated" in res
    assert "/features" in res


@pytest.mark.asyncio
async def test_support_chat_fallback():
    client = TestClient(app)
    
    # Mock OpenRouter API response
    mock_resp_success = MagicMock()
    mock_resp_success.choices = [MagicMock()]
    mock_resp_success.choices[0].message.content = "This is a response."
    mock_resp_success.choices[0].message.tool_calls = None

    from unittest.mock import AsyncMock
    # First client call raises 404 exception, second call succeeds
    mock_create = AsyncMock()
    mock_create.side_effect = [
        Exception("Error code: 404 - No endpoints found"),  # First model with tools fails
        Exception("Error code: 404 - No endpoints found"),  # First model without tools fails
        mock_resp_success                                    # Second model succeeds
    ]

    with patch('openai.resources.chat.completions.AsyncCompletions.create', new=mock_create):
        response = client.post(
            "/api/support-chat",
            json={
                "model": "google/gemma-2-9b-it:free",
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": "read_page_docs"}}]
            }
        )
        assert response.status_code == 200
        assert response.json()["reply"] == "This is a response."
        
        # Verify it was called 3 times in total (1: gemma+tools, 2: gemma-tools, 3: openrouter/free+tools)
        assert mock_create.call_count == 3
