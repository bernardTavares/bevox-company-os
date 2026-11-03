"""Unit tests for lib.provisioners.bot.provision_bot."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.provisioners.bot import provision_bot, BotResult


class TestProvisionBot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.openclaw = Path(self._tmp.name) / "openclaw"
        self.openclaw.mkdir()
        scripts = self.openclaw / "scripts"
        scripts.mkdir()
        # Stub bash script — we mock subprocess.run anyway.
        (scripts / "bootstrap-telegram-agent.sh").write_text(
            "#!/usr/bin/env bash\nexit 0\n"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_required_args_returns_absent(self):
        res = provision_bot(
            "alpha",
            openclaw_dir=self.openclaw,
            bot_port=18000,
            # missing token/chat_id/allow_from
        )
        self.assertIsInstance(res, BotResult)
        self.assertEqual(res.state, "absent")
        self.assertIn("token", res.error or "")

    def test_missing_port_returns_absent(self):
        res = provision_bot(
            "alpha",
            openclaw_dir=self.openclaw,
            bot_port=None,
            token="abc", chat_id="123", allow_from="bernard",
        )
        self.assertEqual(res.state, "absent")
        self.assertIn("bot_port", res.error or "")

    def test_script_missing_returns_absent(self):
        # Remove script
        (self.openclaw / "scripts" / "bootstrap-telegram-agent.sh").unlink()
        res = provision_bot(
            "alpha", openclaw_dir=self.openclaw,
            bot_port=18000, token="t", chat_id="c", allow_from="u",
        )
        self.assertEqual(res.state, "absent")
        self.assertIn("not found", res.error or "")

    def test_happy_path_returns_provisioned(self):
        with patch("lib.provisioners.bot.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout='{"ok":true}', stderr="",
            )
            res = provision_bot(
                "alpha", openclaw_dir=self.openclaw,
                bot_port=18000, token="t", chat_id="c", allow_from="u",
            )
        self.assertEqual(res.state, "provisioned")
        self.assertEqual(res.bot_id, "alpha")
        self.assertEqual(res.bot_port, 18000)
        self.assertIsNotNone(res.profile_dir)

    def test_script_failure_returns_partial(self):
        with patch("lib.provisioners.bot.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=2, stdout="", stderr="bot create failed",
            )
            res = provision_bot(
                "alpha", openclaw_dir=self.openclaw,
                bot_port=18000, token="t", chat_id="c", allow_from="u",
            )
        self.assertEqual(res.state, "partial")
        self.assertIn("bot create failed", res.error or "")

    def test_passes_dry_run_flag(self):
        recorded = {}
        def _capture(cmd, **kwargs):
            recorded["cmd"] = cmd
            return MagicMock(returncode=0, stdout="", stderr="")
        with patch("lib.provisioners.bot.subprocess.run", side_effect=_capture):
            provision_bot(
                "alpha", openclaw_dir=self.openclaw,
                bot_port=18000, token="t", chat_id="c", allow_from="u",
                dry_run=True,
            )
        self.assertIn("--dry-run", recorded["cmd"])


if __name__ == "__main__":
    unittest.main()
