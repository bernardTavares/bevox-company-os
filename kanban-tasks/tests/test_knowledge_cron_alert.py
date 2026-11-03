"""Tests for `openclaw knowledge cron-alert` command (W8 cron alerting)."""
import argparse
import json
import subprocess as _sp
from unittest.mock import patch


def test_cron_alert_dispatches_telegram(tmp_path, monkeypatch):
    """cmd_cron_alert reads journalctl for unit, formats payload, dispatches."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_KNOWLEDGE", "test-token")

    with patch(
        "lib.cli.cmd_knowledge.dispatch_to_telegram", return_value=True,
    ) as m_send, patch.object(_sp, "run") as m_run:
        m_run.return_value.stdout = "mock journal line 1\nmock journal line 2"
        m_run.return_value.returncode = 0

        from lib.cli.cmd_knowledge import cmd_cron_alert
        args = argparse.Namespace(
            target="openclaw-knowledge-watcher.service", json=False,
        )
        rc = cmd_cron_alert(args)

    assert rc == 0
    m_send.assert_called_once()
    payload = m_send.call_args[0][1]
    assert "🚨" in payload
    assert "openclaw-knowledge-watcher.service" in payload
    assert "mock journal" in payload


def test_cron_alert_returns_error_when_no_target():
    from lib.cli.cmd_knowledge import cmd_cron_alert, EXIT_RUNTIME_ERROR
    args = argparse.Namespace(target="", json=False)
    assert cmd_cron_alert(args) == EXIT_RUNTIME_ERROR


def test_cron_alert_handles_journal_failure(tmp_path, monkeypatch):
    """If journalctl fails, alert still dispatches with placeholder."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_KNOWLEDGE", "test-token")

    with patch(
        "lib.cli.cmd_knowledge.dispatch_to_telegram", return_value=True,
    ) as m_send, patch.object(_sp, "run", side_effect=OSError("fail")):
        from lib.cli.cmd_knowledge import cmd_cron_alert
        args = argparse.Namespace(target="x.service", json=False)
        rc = cmd_cron_alert(args)
    assert rc == 0
    payload = m_send.call_args[0][1]
    assert "could not read journal" in payload or "no log lines" in payload
