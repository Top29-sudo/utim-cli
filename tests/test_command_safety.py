import pytest
from utim_cli.tools import analyze_command_safety

def test_analyze_command_safety_destructive():
    destructive_cmds = [
        "rm -rf dist",
        "del /f /q main.exe",
        "rmdir /s /q build",
        "Remove-Item -Recurse ./temp",
        "git clean -fd",
        "python -c \"import os; os.remove('foo.txt')\"",
        "python delete_cache.py",
        "python remove_user.py",
    ]
    for cmd in destructive_cmds:
        is_safe, reason = analyze_command_safety(cmd)
        assert not is_safe, f"Expected '{cmd}' to be marked RISKY, but was safe. Reason: {reason}"

def test_analyze_command_safety_safe_commands():
    safe_cmds = [
        "python script.py",
        "python app.py",
        "python -m pytest",
        "npm run dev",
        "npm install",
        "pip install requests",
        "git status",
        "git commit -m 'feat: update ui'",
        "git push origin main",
        "curl -s https://api.github.com",
        "node index.js",
    ]
    for cmd in safe_cmds:
        is_safe, reason = analyze_command_safety(cmd)
        assert is_safe, f"Expected '{cmd}' to be marked SAFE, but was marked risky. Reason: {reason}"
