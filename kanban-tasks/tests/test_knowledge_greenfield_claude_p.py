"""Tests for greenfield/claude_p.py — subprocess.run mocked, no real claude calls."""
from unittest.mock import MagicMock, patch

import subprocess

from lib.knowledge_watcher.greenfield.claude_p import (
    run_claude_p, DEFAULT_MODEL, DEFAULT_TIMEOUT_S,
)


def test_success_returns_stripped_stdout():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "  hello world  \n"
    fake.stderr = ""
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               return_value=fake) as m_run:
        result = run_claude_p("test prompt")
    assert result == "hello world"
    args, kwargs = m_run.call_args
    assert args[0] == ["claude", "-p", "--model", DEFAULT_MODEL]
    assert kwargs["input"] == "test prompt"
    assert kwargs["timeout"] == DEFAULT_TIMEOUT_S
    assert kwargs["text"] is True


def test_custom_model_passed_through():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "out"
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               return_value=fake) as m_run:
        run_claude_p("p", model="claude-opus-4-7")
    args, _ = m_run.call_args
    assert "claude-opus-4-7" in args[0]


def test_timeout_returns_none():
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=1)):
        result = run_claude_p("p", timeout_s=1)
    assert result is None


def test_cli_not_found_returns_none():
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               side_effect=FileNotFoundError("claude not in PATH")):
        result = run_claude_p("p")
    assert result is None


def test_non_zero_exit_returns_none():
    fake = MagicMock()
    fake.returncode = 1
    fake.stdout = "partial output"
    fake.stderr = "error"
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               return_value=fake):
        result = run_claude_p("p")
    assert result is None


def test_empty_stdout_returns_none():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "   \n  "
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               return_value=fake):
        result = run_claude_p("p")
    assert result is None


def test_oserror_returns_none():
    with patch("lib.knowledge_watcher.greenfield.claude_p.subprocess.run",
               side_effect=OSError("perm denied")):
        result = run_claude_p("p")
    assert result is None
