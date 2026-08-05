import os
import pytest
from utim_cli.tools import resolve_project_path

def test_resolve_project_path_leading_slash():
    cwd = os.getcwd()
    
    # Test path with leading slash (e.g. /social-media-manager/src/scheduler.py)
    rel_path = "/social-media-manager/src/scheduler.py"
    resolved = resolve_project_path(rel_path)
    
    expected = os.path.abspath(os.path.join(cwd, "social-media-manager", "src", "scheduler.py"))
    assert resolved == expected

def test_resolve_project_path_simple_relative():
    cwd = os.getcwd()
    rel_path = "src/index.js"
    resolved = resolve_project_path(rel_path)
    
    expected = os.path.abspath(os.path.join(cwd, "src", "index.js"))
    assert resolved == expected

def test_resolve_project_path_absolute():
    if os.name == "nt":
        abs_path = "C:\\Windows\\System32\\cmd.exe"
        resolved = resolve_project_path(abs_path)
        assert resolved.lower() == abs_path.lower()
    else:
        abs_path = "/tmp/test.txt"
        resolved = resolve_project_path(abs_path)
        assert resolved == abs_path
