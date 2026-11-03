"""Unit tests for lib.provisioners.telegram_topics.provision_telegram_topics."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.provisioners.telegram_topics import (
    provision_telegram_topics, TopicsResult,
)


class TestProvisionTelegramTopics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.openclaw = Path(self._tmp.name) / "openclaw"
        self.openclaw.mkdir()
        scripts = self.openclaw / "scripts"
        scripts.mkdir()
        (scripts / "init_telegram_topics.py").write_text(
            "#!/usr/bin/env python3\nprint('{}')\n"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_script_missing_returns_absent(self):
        (self.openclaw / "scripts" / "init_telegram_topics.py").unlink()
        res = provision_telegram_topics("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "absent")

    def test_creates_two_topics_returns_provisioned(self):
        payload = {
            "created": [
                {"name": "clarifications"},
                {"name": "dispatcher"},
            ],
            "existing": [],
            "failed": [],
        }
        with patch("lib.provisioners.telegram_topics.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(payload), stderr="",
            )
            res = provision_telegram_topics("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "provisioned")
        self.assertEqual(len(res.created), 2)

    def test_existing_topics_return_provisioned(self):
        payload = {
            "created": [],
            "existing": [
                {"name": "clarifications", "thread_id": 1},
                {"name": "dispatcher", "thread_id": 2},
            ],
            "failed": [],
        }
        with patch("lib.provisioners.telegram_topics.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(payload), stderr="",
            )
            res = provision_telegram_topics("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "provisioned")

    def test_failed_topics_return_partial(self):
        payload = {
            "created": [{"name": "clarifications"}],
            "existing": [],
            "failed": [{"name": "dispatcher", "error": "FORBIDDEN"}],
        }
        with patch("lib.provisioners.telegram_topics.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=json.dumps(payload), stderr="",
            )
            res = provision_telegram_topics("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "partial")

    def test_script_failure_returns_absent(self):
        with patch("lib.provisioners.telegram_topics.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=2, stdout="", stderr="missing token",
            )
            res = provision_telegram_topics("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "absent")
        self.assertIn("missing token", res.error or "")


if __name__ == "__main__":
    unittest.main()
