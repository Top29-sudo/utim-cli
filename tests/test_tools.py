import os
from utim_cli.tools import read_file

def test_read_file_directory():
    # .utim is a directory that always exists in the workspace
    res = read_file(".utim")
    assert "is a directory" in res
    assert "use list_directory" in res


def test_parse_xml_tool_calls():
    from utim_cli.client_utils import parse_xml_tool_calls
    import json

    content = (
        "I will now run the command to see the files:\n"
        "<tool_call>\n"
        "shell\n"
        "<arg_key>command</arg_key>\n"
        "<arg_value>find . -type f -name \"*.py\" | head -30</arg_value>\n"
        "</tool_call>\n"
        "Please look at this."
    )
    cleaned, tool_calls = parse_xml_tool_calls(content)
    assert "I will now run the command" in cleaned
    assert "Please look at this." in cleaned
    assert "<tool_call>" not in cleaned

    assert len(tool_calls) == 1
    tc = tool_calls[0]
    assert tc["function"]["name"] == "run_command"
    args = json.loads(tc["function"]["arguments"])
    assert args["command"] == "find . -type f -name \"*.py\" | head -30"


def test_experience_reflection():
    from utim_cli.reflection import ExperienceManager, extract_context_from_interaction, experience_based_reflection

    # Test rule-based extraction
    ctx = extract_context_from_interaction(
        "I will sit on the stool near the wall",
        "This simulates a chair back support and provides back support"
    )
    assert "stool" in ctx["objects"]
    assert "wall" in ctx["objects"]
    assert ctx["relationships"]["provides_back_support"] is True
    assert ctx["relationships"]["simulates_chair_back"] is True

    # Test ExperienceManager patterns matching
    mgr = ExperienceManager(storage_path=".utim_tmp/test_experience_memory.json")
    mgr.add_experience(
        pattern_id="stool_wall_relationship",
        description="Stool + wall = simulated chair experience",
        pattern_type="relationship",
        objects=["stool", "wall"],
        relationships={"simulates_chair_back": True, "provides_back_support": True},
        strength=0.7
    )
    # Retrieve patterns for stool + wall
    related = mgr.get_related_experiences(["stool", "wall"], {"provides_back_support": True, "simulates_chair_back": True})
    assert len(related) > 0
    # The stool_wall_relationship pattern should match
    matches = [node for node in related if node.pattern_id == "stool_wall_relationship"]
    assert len(matches) == 1
    node = matches[0]
    assert node.pattern_type == "relationship"

    # Test learn and update pattern strength
    old_strength = node.strength
    mgr.learn_from_experience(
        context={"objects": ["stool", "wall"], "relationships": {"provides_back_support": True, "simulates_chair_back": True}},
        outcome="simulates a chair back support and provides back support",
        success=True
    )
    # Strength should increase on success feedback
    assert node.strength >= old_strength

    # Clean up test file
    if os.path.exists(".utim_tmp/test_experience_memory.json"):
        try:
            os.remove(".utim_tmp/test_experience_memory.json")
        except Exception:
            pass


def test_orchestrator_experience_injection():
    from utim_cli.reflection import experience_manager
    analysis = experience_manager.analyze_pattern(
        ["stool", "wall"], 
        {"provides_back_support": True, "simulates_chair_back": True}
    )
    assert analysis["confidence"] > 0.4
    assert len(analysis["suggestions"]) > 0
    assert any("stool" in s.lower() or "wall" in s.lower() for s in analysis["suggestions"])


def test_generate_image_error_parsing():
    from unittest.mock import patch, MagicMock
    import requests
    from utim_cli.tools import generate_image
    
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = '{"detail":{"message":"Monthly credit quota exceeded.","reset_at":"2026-07-27T07:04:15.709176Z","upgrade_url":"https://utim.dev/upgrade"}}'
    mock_response.json.return_value = {
        "detail": {
            "message": "Monthly credit quota exceeded.",
            "reset_at": "2026-07-27T07:04:15.709176Z",
            "upgrade_url": "https://utim.dev/upgrade"
        }
    }
    
    http_error = requests.exceptions.HTTPError("429 Client Error", response=mock_response)
    
    with patch("utim_cli.config.config.get", return_value="mock_api_key"), \
         patch("requests.post", side_effect=http_error):
        result = generate_image("mountain landscape")
        assert "Monthly credit quota exceeded." in result
        assert "2026-07-27T07:04:15.709176Z" in result
        assert "https://utim.dev/upgrade" in result
        assert "429 Client Error" not in result
def test_clean_clixml():
    from utim_cli.tools import clean_clixml
    
    clixml_input = (
        '#< CLIXML\r\n'
        '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">'
        '<Obj S="progress" RefId="0"><TN RefId="0"><T>System.Management.Automation.PSCustomObject</T></TN></Obj>'
        '<S S="Error">Get-ChildItem : A parameter cannot be found that matches parameter name \'la\'._x000D__x000A_</S>'
        '<S S="Error">At line:1 char:4_x000D__x000A_</S>'
        '</Objs>'
    )
    
    cleaned = clean_clixml(clixml_input)
    assert "Get-ChildItem" in cleaned
    assert "matches parameter name 'la'" in cleaned
    assert "At line:1 char:4" in cleaned
    assert "_x000D_" not in cleaned
    assert "<Objs" not in cleaned
    assert "CLIXML" not in cleaned
