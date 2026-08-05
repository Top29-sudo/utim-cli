import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from utim_cli.harbor import UtimHarborAgent
from utim_cli.utim import run_headless_task


def test_harbor_agent_instantiation():
    agent = UtimHarborAgent(model_name="test-model")
    assert agent.model_name == "test-model"


def test_harbor_agent_env_fallback(monkeypatch):
    monkeypatch.setenv("UTIM_MODEL", "env-model")
    agent = UtimHarborAgent()
    assert agent.model_name == "env-model"


@patch("utim_cli.orchestrator.Orchestrator.run_task")
def test_run_headless_task_success(mock_run_task, monkeypatch):
    monkeypatch.setenv("UTIM_API_KEY", "test-key")
    exit_code = run_headless_task("print hello", dry_run=True)
    assert exit_code == 0
    mock_run_task.assert_called_once_with("print hello")


@patch("utim_cli.orchestrator.Orchestrator.run_task")
def test_harbor_agent_run(mock_run_task, monkeypatch):
    import asyncio
    monkeypatch.setenv("UTIM_API_KEY", "test-key")
    agent = UtimHarborAgent()
    res = asyncio.run(agent.run("test task"))
    assert res["status"] == "completed"
    assert res["exit_code"] == 0
    mock_run_task.assert_called_once_with("test task")
