"""Tests for ~/.openclaw/scripts/bootstrap-telegram-agent.sh non-interactive mode.

Uses HOME override + --dry-run to avoid systemd side-effects.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path.home() / ".openclaw" / "scripts" / "bootstrap-telegram-agent.sh"


def _make_fake_home() -> Path:
    """Build a temp HOME with the minimum structure the script preflights for."""
    tmp = Path(tempfile.mkdtemp(prefix="bootstrap-test-"))
    shared = tmp / ".openclaw" / "workspace-shared" / "memory"
    shared.mkdir(parents=True)
    (shared / "user_profile.md").write_text("# user\n")
    (shared / "feedback_universal.md").write_text("# fb\n")
    (shared / "reference_bevox_knowledge.md").write_text("# ref\n")
    template = tmp / ".openclaw" / "openclaw.json"
    template.write_text(json.dumps({
        "agents": {"defaults": {"workspace": "x"}, "list": []},
        "channels": {},
        "plugins": {"allow": []},
    }))
    return tmp


def _run(tmp_home: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(tmp_home)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True, text=True, env=env, timeout=15,
    )


class BootstrapNonInteractiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = _make_fake_home()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_non_interactive_requires_token(self) -> None:
        r = _run(self.tmp, "--non-interactive", "--json", "testarea", "18999")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("--token", r.stderr)

    def test_dry_run_writes_config_and_emits_json(self) -> None:
        r = _run(
            self.tmp,
            "--token", "1234567890:AAFakeToken_FakeToken_FakeToken_xyz",
            "--chat-id", "-100123456789",
            "--allow-from", "111,222",
            "--skills", "knowledge-sync-commands,clarification-commands",
            "--non-interactive", "--json", "--dry-run",
            "testarea", "18999",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        # JSON line is the last stdout line
        last = r.stdout.strip().splitlines()[-1]
        payload = json.loads(last)
        self.assertTrue(payload["success"])
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["area"], "testarea")
        self.assertEqual(payload["port"], 18999)
        # Profile config was written with our values
        cfg = json.loads((self.tmp / ".openclaw-testarea" / "openclaw.json").read_text())
        tg = cfg["channels"]["telegram"]
        self.assertEqual(tg["botToken"], "1234567890:AAFakeToken_FakeToken_FakeToken_xyz")
        self.assertIn("-100123456789", tg["groups"])
        self.assertEqual(tg["allowFrom"], ["111", "222"])
        self.assertIn("knowledge-sync-commands", cfg["plugins"]["allow"])
        self.assertIn("clarification-commands", cfg["plugins"]["allow"])

    def test_dry_run_idempotent_re_run_overwrites(self) -> None:
        common = [
            "--non-interactive", "--json", "--dry-run",
            "--allow-from", "111",
            "--skills", "knowledge-sync-commands",
        ]
        # First with one token
        r1 = _run(
            self.tmp, "--token", "1111111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "--chat-id", "-100111", *common, "testarea", "18999",
        )
        self.assertEqual(r1.returncode, 0, r1.stderr)
        # Second with different token (reconnect)
        r2 = _run(
            self.tmp, "--token", "2222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "--chat-id", "-100222", *common, "testarea", "18999",
        )
        self.assertEqual(r2.returncode, 0, r2.stderr)
        cfg = json.loads((self.tmp / ".openclaw-testarea" / "openclaw.json").read_text())
        tg = cfg["channels"]["telegram"]
        # Second run wins
        self.assertEqual(tg["botToken"], "2222222222:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")
        self.assertIn("-100222", tg["groups"])
        self.assertNotIn("-100111", tg["groups"])

    def test_skills_csv_always_includes_knowledge_sync(self) -> None:
        # User passes only clarification-commands; knowledge-sync should be force-prepended
        r = _run(
            self.tmp, "--token", "1234567890:AAFakeToken_FakeToken_FakeToken_xyz",
            "--chat-id", "-100123",
            "--allow-from", "111",
            "--skills", "clarification-commands",
            "--non-interactive", "--json", "--dry-run",
            "testarea", "18999",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = json.loads((self.tmp / ".openclaw-testarea" / "openclaw.json").read_text())
        self.assertIn("knowledge-sync-commands", cfg["plugins"]["allow"])
        self.assertIn("clarification-commands", cfg["plugins"]["allow"])

    def test_interactive_mode_unchanged_no_token_required(self) -> None:
        # Running without --non-interactive should still create placeholder config
        r = _run(self.tmp, "testarea", "18999")
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = json.loads((self.tmp / ".openclaw-testarea" / "openclaw.json").read_text())
        tg = cfg["channels"]["telegram"]
        self.assertIn("<POPULATE_CHAT_ID>", tg["groups"])
        self.assertEqual(tg["allowFrom"], ["<POPULATE_BERNARD_USER_ID>"])
        self.assertNotIn("botToken", tg)


if __name__ == "__main__":
    unittest.main()
