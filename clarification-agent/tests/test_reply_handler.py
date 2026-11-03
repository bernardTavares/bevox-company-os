"""Tests reply_handler.handle_reply — schema v2 status update."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import reply_handler, store


class TestHandleReplyUpdatesStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = Path(self.tmpdir) / "notifier-state.json"
        # Seed v2 entry pending
        state = {
            "schema_version": 2,
            "heartbeat_at": None,
            "notifications": {
                "T-7777-clr-1": {
                    "task_id": "T-7777",
                    "project": "bevox-site",
                    "token_alias": "project-bevox-site",
                    "chat_id": "-100xxx",
                    "thread_id": 18,
                    "telegram_message_id": 999,
                    "sent_at": "2026-04-28T10:00:00Z",
                    "status": "pending",
                    "resolved_at": None,
                    "resolved_via": None,
                }
            }
        }
        self.state_path.write_text(json.dumps(state))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_handle_reply_marks_resolved(self):
        with patch.object(store, "ROOT", Path(self.tmpdir)):
            with patch.object(reply_handler, "unblock_task", return_value=True) as mock_unblock:
                with patch.object(reply_handler, "send_confirmation_message") as mock_confirm:
                    with patch.object(reply_handler, "lifecycle") as mock_lifecycle:
                        with patch.object(reply_handler.store, "emit_signal"):
                            success = reply_handler.handle_reply(
                                "T-7777-clr-1", "Opção A",
                                source="telegram_reply",
                            )
        self.assertTrue(success)
        data = json.loads(self.state_path.read_text())
        entry = data["notifications"]["T-7777-clr-1"]
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["resolved_via"], "telegram_reply")
        self.assertIsNotNone(entry["resolved_at"])
        # Verify lifecycle and confirmation were invoked
        mock_lifecycle.merge_dispatch_payload.assert_called_once()
        merge_args = mock_lifecycle.merge_dispatch_payload.call_args
        self.assertEqual(merge_args[0][0], "T-7777")  # task_id
        self.assertEqual(merge_args[0][1]["last_clarification_source"], "telegram_reply")
        mock_unblock.assert_called_once_with("T-7777-clr-1")
        mock_confirm.assert_called_once_with("T-7777-clr-1", "T-7777")

    def test_handle_reply_idempotent_on_already_resolved(self):
        # Pre-seed as resolved
        state = json.loads(self.state_path.read_text())
        state["notifications"]["T-7777-clr-1"]["status"] = "resolved"
        state["notifications"]["T-7777-clr-1"]["resolved_at"] = "2026-04-28T11:00:00Z"
        self.state_path.write_text(json.dumps(state))

        with patch.object(store, "ROOT", Path(self.tmpdir)):
            with patch.object(reply_handler, "unblock_task", return_value=True) as mock_unblock:
                with patch.object(reply_handler, "send_confirmation_message"):
                    success = reply_handler.handle_reply(
                        "T-7777-clr-1", "Opção B",
                        source="telegram_reply",
                    )

        # Skipped → unblock not called second time
        mock_unblock.assert_not_called()
        self.assertTrue(success)  # idempotent: returns True


class TestConfirmationRouting(unittest.TestCase):
    def test_resolve_token_for_alias_central(self):
        from lib import reply_handler
        env = {"TELEGRAM_BOT_TOKEN": "CENTRAL"}
        self.assertEqual(reply_handler._resolve_token_for_alias("openclaw-central", env), "CENTRAL")

    def test_resolve_token_for_alias_project_voz_naming(self):
        from lib import reply_handler
        env = {"BOT_TOKEN_VOZ_BEVOX_SITE": "PROJECT_TOK"}
        self.assertEqual(
            reply_handler._resolve_token_for_alias("project-bevox-site", env),
            "PROJECT_TOK",
        )

    def test_resolve_token_for_alias_project_short_naming(self):
        from lib import reply_handler
        env = {"BOT_TOKEN_BEVOX_SITE": "PROJECT_TOK"}
        self.assertEqual(
            reply_handler._resolve_token_for_alias("project-bevox-site", env),
            "PROJECT_TOK",
        )

    def test_resolve_token_for_alias_unknown_returns_none(self):
        from lib import reply_handler
        self.assertIsNone(reply_handler._resolve_token_for_alias("project-unknown", {}))
        self.assertIsNone(reply_handler._resolve_token_for_alias(None, {}))

    def test_send_confirmation_uses_entry_token_alias(self):
        import tempfile, json
        from pathlib import Path
        from unittest.mock import patch
        from lib import reply_handler, store

        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            state_path = tmpdir / "notifier-state.json"
            state = {
                "schema_version": 2,
                "notifications": {
                    "T-5555-clr-1": {
                        "task_id": "T-5555",
                        "token_alias": "project-bevox-site",
                        "chat_id": "-100site",
                        "thread_id": 18,
                        "telegram_message_id": 50,
                        "status": "pending",
                    }
                }
            }
            state_path.write_text(json.dumps(state))

            sent_calls = []
            def fake_send_via_token(token, payload):
                sent_calls.append({"token": token, "payload": payload})
                return True

            with patch.object(store, "ROOT", tmpdir):
                with patch.object(reply_handler, "_send_via_token", side_effect=fake_send_via_token):
                    with patch.object(reply_handler, "load_env",
                                      return_value={"BOT_TOKEN_VOZ_BEVOX_SITE": "PROJECT_TOK"}):
                        reply_handler.send_confirmation_message("T-5555-clr-1", "T-5555")

        self.assertEqual(len(sent_calls), 1)
        self.assertEqual(sent_calls[0]["token"], "PROJECT_TOK")
        self.assertEqual(sent_calls[0]["payload"]["chat_id"], "-100site")
        self.assertEqual(sent_calls[0]["payload"]["message_thread_id"], 18)
        self.assertIn("T-5555-clr-1", sent_calls[0]["payload"]["text"])

    def test_send_confirmation_skips_when_no_alias(self):
        import tempfile, json
        from pathlib import Path
        from unittest.mock import patch
        from lib import reply_handler, store

        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            state_path = tmpdir / "notifier-state.json"
            # Orphan-shaped entry: no alias / chat_id
            state = {
                "schema_version": 2,
                "notifications": {
                    "T-9999-clr-1": {
                        "task_id": "T-9999",
                        "token_alias": None,
                        "chat_id": None,
                        "status": "orphan",
                    }
                }
            }
            state_path.write_text(json.dumps(state))

            with patch.object(store, "ROOT", tmpdir):
                with patch.object(reply_handler, "_send_via_token") as mock_send:
                    reply_handler.send_confirmation_message("T-9999-clr-1", "T-9999")
                mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
