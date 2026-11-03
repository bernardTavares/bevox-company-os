"""Testes notifier.py — standalone Telegram notifier."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib import notifier


class TestParseFilename(unittest.TestCase):
    def test_valid_filename_returns_task_and_cid(self):
        task_id, cid = notifier.parse_escalation_filename("T-0006-clr-2.md")
        self.assertEqual(task_id, "T-0006")
        self.assertEqual(cid, "T-0006-clr-2")

    def test_double_digit_clr_number(self):
        task_id, cid = notifier.parse_escalation_filename("T-0042-clr-15.md")
        self.assertEqual(task_id, "T-0042")
        self.assertEqual(cid, "T-0042-clr-15")

    def test_invalid_filename_raises(self):
        with self.assertRaises(ValueError):
            notifier.parse_escalation_filename("garbage.md")


class TestState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / "notifier-state.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_load_missing_returns_empty_shape(self):
        s = notifier.load_state(self.state_path)
        self.assertEqual(s["schema_version"], 2)  # bumped in Task 4 (v2 write path)
        self.assertEqual(s["notifications"], {})

    def test_save_then_load_roundtrip(self):
        s = {
            "schema_version": 1,
            "heartbeat_at": "2026-04-22T00:05:00Z",
            "notifications": {
                "T-0006-clr-2": {
                    "task_id": "T-0006",
                    "notified_at": "2026-04-21T21:41:15Z",
                    "telegram_message_id": 42,
                    "source_path": "/tmp/x",
                },
            },
        }
        notifier.save_state(self.state_path, s)
        loaded = notifier.load_state(self.state_path)
        self.assertEqual(loaded, s)

    def test_save_is_atomic_no_partial(self):
        """Arquivo nunca fica parcialmente escrito (usa tmp+rename)."""
        s = {"schema_version": 1, "heartbeat_at": "x", "notifications": {"a": {"x": 1}}}
        notifier.save_state(self.state_path, s)
        # Arquivo existe e é válido JSON
        with open(self.state_path) as f:
            parsed = json.load(f)
        self.assertEqual(parsed, s)

    def test_corrupt_file_returns_empty(self):
        self.state_path.write_text("{not valid json")
        s = notifier.load_state(self.state_path)
        self.assertEqual(s["notifications"], {})


class TestBuildMessage(unittest.TestCase):
    def test_body_contains_task_id_and_clarification_id(self):
        """Verify task_id and clarification_id are visible in the message body."""
        body = notifier.build_telegram_message(
            task_id="T-1234",
            cid="T-1234-clr-2",
            chat_id="-100",
            thread_id=18,
        )
        self.assertIn("T-1234", body["text"])
        self.assertIn("T-1234-clr-2", body["text"])

    def test_body_includes_response_instruction_with_cid(self):
        """Verify the response instruction cites the clarification_id."""
        body = notifier.build_telegram_message("T-1234", "T-1234-clr-2", "-100", 18)
        # The response instruction must include the cid (used by the plugin's
        # reply-to-message inference and Bernard's manual reply).
        self.assertIn("T-1234-clr-2:", body["text"])


class TestValidateEnv(unittest.TestCase):
    def test_all_present_returns_tuple(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "abc:xyz",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-100XXXXXXXXXX",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "42",
        }
        token, chat_id, thread_id = notifier.validate_env(env)
        self.assertEqual(token, "abc:xyz")
        self.assertEqual(chat_id, "-100XXXXXXXXXX")
        self.assertEqual(thread_id, 42)

    def test_missing_token_raises(self):
        env = {
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-1",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "1",
        }
        with self.assertRaises(notifier.EnvError) as ctx:
            notifier.validate_env(env)
        self.assertIn("TELEGRAM_BOT_TOKEN", str(ctx.exception))

    def test_non_integer_thread_id_raises(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "t",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-1",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "not_a_number",
        }
        with self.assertRaises(notifier.EnvError):
            notifier.validate_env(env)


class TestSendTelegram(unittest.TestCase):
    def test_happy_path_returns_ok_and_message_id(self):
        body = {
            "chat_id": "-1", "message_thread_id": 1,
            "text": "x", "disable_web_page_preview": True,
        }
        fake_response = json.dumps({
            "ok": True,
            "result": {"message_id": 4242, "chat": {"id": -1}, "text": "x"},
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("lib.notifier.urllib.request.urlopen", return_value=mock_resp):
            ok, result = notifier.send_telegram_message(body, token="abc:xyz")
        self.assertTrue(ok)
        self.assertEqual(result["message_id"], 4242)
        self.assertIsNone(result.get("error"))

    def test_body_has_unicode_is_json_encoded_safely(self):
        body = {
            "chat_id": "-1", "message_thread_id": 1,
            "text": "🚫 special chars: \"\\n", "disable_web_page_preview": True,
        }
        fake_response = json.dumps({
            "ok": True, "result": {"message_id": 1},
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("lib.notifier.urllib.request.urlopen", return_value=mock_resp) as m:
            ok, _ = notifier.send_telegram_message(body, token="t")
        self.assertTrue(ok)
        # Confirma que o body foi serializado e o token apareceu na URL
        req = m.call_args[0][0]
        self.assertIn("/bott/sendMessage", req.full_url)
        posted = json.loads(req.data.decode("utf-8"))
        self.assertEqual(posted["text"], body["text"])


class TestSendTelegramErrors(unittest.TestCase):
    def _body(self):
        return {"chat_id": "-1", "message_thread_id": 1,
                "text": "x", "disable_web_page_preview": True}

    def test_http_400_returns_classified_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x", code=400, msg="Bad Request",
            hdrs=None, fp=None,
        )
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_400")

    def test_http_429_rate_limit(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x", code=429, msg="Too Many Requests",
            hdrs=None, fp=None,
        )
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_429")

    def test_http_500_returns_classified_error(self):
        import urllib.error
        err = urllib.error.HTTPError(
            url="http://x", code=500, msg="Internal Server Error",
            hdrs=None, fp=None,
        )
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_500")

    def test_network_down_returns_classified_error(self):
        import urllib.error
        err = urllib.error.URLError("DNS failure")
        with patch("lib.notifier.urllib.request.urlopen", side_effect=err):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_network")

    def test_response_not_ok_classified(self):
        fake = json.dumps({"ok": False, "description": "bad thread"}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch("lib.notifier.urllib.request.urlopen", return_value=mock_resp):
            ok, result = notifier.send_telegram_message(self._body(), token="t")
        self.assertFalse(ok)
        self.assertEqual(result["error"], "telegram_api_not_ok")
        self.assertEqual(result["body"]["description"], "bad thread")


class TestScanAndDiff(unittest.TestCase):
    def test_scan_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            out = notifier.scan_escalations(Path(d))
            self.assertEqual(out, [])

    def test_scan_returns_cids_sorted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "T-0008-clr-2.md").touch()
            (p / "T-0006-clr-1.md").touch()
            (p / "T-0006-clr-2.md").touch()
            (p / "ignored.txt").touch()
            (p / "not-escalation.md").touch()
            out = notifier.scan_escalations(p)
            self.assertEqual([c[1] for c in out],
                             ["T-0006-clr-1", "T-0006-clr-2", "T-0008-clr-2"])
            # each entry is (task_id, cid, source_path)
            self.assertEqual(out[0][0], "T-0006")
            self.assertTrue(out[0][2].endswith("T-0006-clr-1.md"))

    def test_compute_diff_detects_new_and_resolved(self):
        pending = {"A", "B", "C"}
        state_cids = {"A", "D"}
        new, resolved = notifier.compute_diff(pending, state_cids)
        self.assertEqual(new, {"B", "C"})
        self.assertEqual(resolved, {"D"})


class TestAppendEvent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jsonl = Path(self.tmp) / "notifier.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_append_writes_single_line_json(self):
        notifier.append_event(self.jsonl, "tick_started", {"pending_count": 2})
        lines = self.jsonl.read_text().strip().splitlines()
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["event"], "tick_started")
        self.assertEqual(parsed["payload"]["pending_count"], 2)
        self.assertIn("ts", parsed)

    def test_multiple_appends_keep_order(self):
        notifier.append_event(self.jsonl, "a", {"n": 1})
        notifier.append_event(self.jsonl, "b", {"n": 2})
        notifier.append_event(self.jsonl, "c", {"n": 3})
        lines = self.jsonl.read_text().strip().splitlines()
        self.assertEqual([json.loads(l)["event"] for l in lines], ["a", "b", "c"])

    def test_iso_timestamp_format(self):
        notifier.append_event(self.jsonl, "x", {})
        line = self.jsonl.read_text().strip()
        parsed = json.loads(line)
        # ISO 8601 UTC with Z
        self.assertRegex(parsed["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class TestTick(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.esc_dir = self.tmp / "escalations"
        self.esc_dir.mkdir()
        self.state_path = self.tmp / "notifier-state.json"
        self.jsonl = self.tmp / "notifier.jsonl"
        # 2 escalations pending
        (self.esc_dir / "T-0006-clr-2.md").touch()
        (self.esc_dir / "T-0008-clr-1.md").touch()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def _mock_send(self, message_id=42):
        """Patch that always returns (True, {"message_id": message_id})."""
        return patch(
            "lib.notifier.send_telegram_message",
            return_value=(True, {"message_id": message_id}),
        )

    def test_first_tick_sends_both_and_updates_state(self):
        with self._mock_send():
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["skipped_already"], 0)
        self.assertEqual(result["skipped_resolved"], 0)
        state = notifier.load_state(self.state_path)
        self.assertIn("T-0006-clr-2", state["notifications"])
        self.assertIn("T-0008-clr-1", state["notifications"])

    def test_second_tick_skips_already_sent(self):
        with self._mock_send():
            notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["skipped_already"], 2)

    def test_dry_run_does_not_send_nor_write_state(self):
        with self._mock_send() as m:
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=True,
            )
        m.assert_not_called()
        self.assertFalse(self.state_path.exists())
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["would_send"], 2)

    def test_send_failure_skips_and_retries_next_tick(self):
        # First tick: send fails for one of them
        call_count = [0]
        def flaky(body, token):
            call_count[0] += 1
            if call_count[0] == 1:
                return False, {"error": "telegram_api_500"}
            return True, {"message_id": call_count[0]}
        with patch("lib.notifier.send_telegram_message", side_effect=flaky):
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        # 1 sent, 1 failed — state has only the sent one
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)
        state = notifier.load_state(self.state_path)
        self.assertEqual(len(state["notifications"]), 1)


class TestGCAndLock(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.esc_dir = self.tmp / "escalations"
        self.esc_dir.mkdir()
        self.state_path = self.tmp / "notifier-state.json"
        self.jsonl = self.tmp / "notifier.jsonl"
        self.lock_path = self.tmp / "notifier.lock"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_resolved_cid_is_gc_without_message(self):
        # Seed state with cid that is no longer in escalations dir
        state = {
            "schema_version": 1, "heartbeat_at": None,
            "notifications": {
                "T-0001-clr-1": {
                    "task_id": "T-0001", "notified_at": "2026-01-01T00:00:00Z",
                    "telegram_message_id": 1, "source_path": "/gone",
                },
            },
        }
        notifier.save_state(self.state_path, state)

        with patch("lib.notifier.send_telegram_message") as m:
            m.return_value = (True, {"message_id": 99})
            result = notifier.tick(
                escalations_dir=self.esc_dir,
                state_path=self.state_path,
                jsonl_path=self.jsonl,
                token="t", chat_id="-1", thread_id=1,
                dry_run=False,
            )
        m.assert_not_called()  # no send because resolved
        self.assertEqual(result["skipped_resolved"], 1)
        # Schema v2: entry is PRESERVED with status="resolved" (audit history),
        # not popped. resolved_via="escalation_removed" when neither cmd_answer
        # nor cmd_override set it.
        post = notifier.load_state(self.state_path)
        self.assertIn("T-0001-clr-1", post["notifications"])
        entry = post["notifications"]["T-0001-clr-1"]
        self.assertEqual(entry["status"], "resolved")
        self.assertEqual(entry["resolved_via"], "escalation_removed")
        self.assertIsNotNone(entry.get("resolved_at"))

    def test_acquire_lock_blocks_concurrent_attempt(self):
        # First acquire succeeds
        fd = notifier.acquire_lock(self.lock_path)
        self.assertIsNotNone(fd)
        # Second acquire (same process, non-blocking) returns None
        fd2 = notifier.acquire_lock(self.lock_path)
        self.assertIsNone(fd2)
        notifier.release_lock(fd)


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env_patch = patch.dict(os.environ, {
            "OPENCLAW_CLARIFICATION_DIR": str(self.tmp),
            "TELEGRAM_BOT_TOKEN": "abc:xyz",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "-100XXXXXXXXXX",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "42",
        }, clear=False)
        self.env_patch.start()
        (self.tmp / "escalations").mkdir()

    def tearDown(self):
        self.env_patch.stop()
        import shutil
        shutil.rmtree(self.tmp)

    def test_main_tick_happy_exits_zero(self):
        with patch("lib.notifier.send_telegram_message",
                   return_value=(True, {"message_id": 1})):
            rc = notifier.main(["--tick"])
        self.assertEqual(rc, 0)

    def test_main_missing_env_exits_one(self):
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CLARIFICATIONS_CHAT_ID": "",
            "TELEGRAM_CLARIFICATIONS_THREAD_ID": "",
        }, clear=False):
            rc = notifier.main(["--tick"])
        self.assertEqual(rc, 1)

    def test_main_dry_run_does_not_send(self):
        (self.tmp / "escalations" / "T-0006-clr-2.md").touch()
        with patch("lib.notifier.send_telegram_message") as m:
            rc = notifier.main(["--tick", "--dry-run"])
        m.assert_not_called()
        self.assertEqual(rc, 0)

    def test_main_json_outputs_parseable_summary(self):
        import io
        stdout_capture = io.StringIO()
        with patch("lib.notifier.send_telegram_message",
                   return_value=(True, {"message_id": 1})), \
             patch("sys.stdout", stdout_capture):
            rc = notifier.main(["--tick", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(stdout_capture.getvalue())
        self.assertIn("sent", parsed)


class TestSlugForClarification(unittest.TestCase):
    """Phase 4: per-project topic resolution via projects-meta.json."""

    def test_slug_for_clarification_reads_question_frontmatter(self):
        """_slug_for_clarification reads project: from question frontmatter."""
        with patch.object(notifier, "_slug_for_clarification",
                          lambda task_id, cid: "smoke-proj"
                          if task_id == "T-0099" and cid == "T-0099-clr-1"
                          else None):
            self.assertEqual(
                notifier._slug_for_clarification("T-0099", "T-0099-clr-1"),
                "smoke-proj",
            )

    def test_meta_thread_id_overrides_env(self):
        """When meta has clarifications topic, resolve returns the override."""
        with patch.object(notifier, "resolve_thread_id",
                          lambda slug, topic: 555 if topic == "clarifications" else None):
            self.assertEqual(
                notifier.resolve_thread_id("smoke-proj", "clarifications"),
                555,
            )

    def test_meta_lookup_returns_none_falls_back_to_env(self):
        """When meta has no topic, resolve_thread_id returns None (fallback path)."""
        with patch.object(notifier, "resolve_thread_id", lambda *a, **kw: None):
            self.assertIsNone(notifier.resolve_thread_id("any", "clarifications"))


class TestNotifierWritesSchemaV2(unittest.TestCase):
    def test_tick_writes_v2_entry_with_token_alias_and_status(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            esc_dir = Path(td) / "escalations"
            esc_dir.mkdir()
            (esc_dir / "T-9999-clr-1.md").write_text("dummy")
            state_path = Path(td) / "notifier-state.json"
            jsonl_path = Path(td) / "notifier.jsonl"

            with patch.object(notifier, "send_telegram_message",
                              return_value=(True, {"message_id": 555})):
                notifier.tick(
                    escalations_dir=esc_dir,
                    state_path=state_path,
                    jsonl_path=jsonl_path,
                    token="TOK", chat_id="-100abc", thread_id=18,
                )

            data = json.loads(state_path.read_text())
            self.assertEqual(data.get("schema_version"), 2)
            entry = data["notifications"]["T-9999-clr-1"]
            self.assertEqual(entry["telegram_message_id"], 555)
            self.assertEqual(entry["chat_id"], "-100abc")
            self.assertEqual(entry["thread_id"], 18)
            self.assertEqual(entry["status"], "pending")
            self.assertIn("sent_at", entry)
            self.assertEqual(entry["token_alias"], "openclaw-central")
            self.assertIsNone(entry["resolved_at"])
            self.assertIsNone(entry["resolved_via"])

    def test_alias_for_central_when_token_matches_default(self):
        # Same token used = central path
        result = notifier._alias_for("bevox-site", "TOK_DEFAULT", "TOK_DEFAULT")
        self.assertEqual(result, "openclaw-central")

    def test_alias_for_project_when_token_differs(self):
        result = notifier._alias_for("bevox-site", "PROJECT_TOKEN", "DEFAULT_TOKEN")
        self.assertEqual(result, "project-bevox-site")

    def test_alias_for_central_when_no_slug(self):
        result = notifier._alias_for(None, "ANY", "ANY")
        self.assertEqual(result, "openclaw-central")


class TestNotifierFallbackToCentral(unittest.TestCase):
    def test_fallback_event_emitted_when_resolve_returns_none(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            esc_dir = Path(td) / "escalations"
            esc_dir.mkdir()
            (esc_dir / "T-8888-clr-1.md").write_text("dummy")
            state_path = Path(td) / "notifier-state.json"
            jsonl_path = Path(td) / "notifier.jsonl"

            # Stub _slug_for_clarification to return a slug, and stub
            # resolve_telegram_target to return None (simulating projects-meta
            # without topics.clarifications).
            fake_module = type(sys)("telegram_meta")
            fake_module.resolve_telegram_target = lambda slug, topic: None

            with patch.dict("sys.modules", {"telegram_meta": fake_module}):
                with patch.object(notifier, "send_telegram_message",
                                  return_value=(True, {"message_id": 100})):
                    with patch.object(notifier, "_slug_for_clarification",
                                      return_value="bevox-site"):
                        notifier.tick(
                            escalations_dir=esc_dir,
                            state_path=state_path,
                            jsonl_path=jsonl_path,
                            token="CENTRAL_TOK", chat_id="-100central", thread_id=99,
                        )

            # Verify entry was written using central (fallback path)
            data = json.loads(state_path.read_text())
            entry = data["notifications"]["T-8888-clr-1"]
            self.assertEqual(entry["chat_id"], "-100central")
            self.assertEqual(entry["thread_id"], 99)
            self.assertEqual(entry["token_alias"], "openclaw-central")

            # Verify fallback event was logged
            with open(jsonl_path) as f:
                events = [json.loads(line) for line in f if line.strip()]
            fallback = next(e for e in events if e["event"] == "clarification_fallback_to_central")
            self.assertEqual(fallback["payload"]["project"], "bevox-site")
            self.assertEqual(fallback["payload"]["task_id"], "T-8888")
            self.assertEqual(fallback["payload"]["clarification_id"], "T-8888-clr-1")
            self.assertIn("topics.clarifications missing", fallback["payload"]["reason"])


    def test_fallback_event_emitted_when_telegram_meta_import_fails(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            esc_dir = Path(td) / "escalations"
            esc_dir.mkdir()
            (esc_dir / "T-7777-clr-1.md").write_text("dummy")
            state_path = Path(td) / "notifier-state.json"
            jsonl_path = Path(td) / "notifier.jsonl"

            # Force the import to fail by removing telegram_meta from sys.modules
            # AND making it raise ImportError on import attempt.
            class _RaisingFinder:
                def find_spec(self, name, *args, **kwargs):
                    if name == "telegram_meta":
                        raise ImportError("forced for test")
                    return None

            import sys as _sys
            existing = _sys.modules.pop("telegram_meta", None)
            _sys.meta_path.insert(0, _RaisingFinder())
            try:
                with patch.object(notifier, "send_telegram_message",
                                  return_value=(True, {"message_id": 200})):
                    with patch.object(notifier, "_slug_for_clarification",
                                      return_value="bevox-mobile"):
                        notifier.tick(
                            escalations_dir=esc_dir,
                            state_path=state_path,
                            jsonl_path=jsonl_path,
                            token="CENTRAL_TOK", chat_id="-100central", thread_id=99,
                        )
            finally:
                _sys.meta_path.pop(0)
                if existing is not None:
                    _sys.modules["telegram_meta"] = existing

            with open(jsonl_path) as f:
                events = [json.loads(line) for line in f if line.strip()]
            fallback_events = [e for e in events if e["event"] == "clarification_fallback_to_central"]
            self.assertEqual(len(fallback_events), 1)
            payload = fallback_events[0]["payload"]
            self.assertEqual(payload["reason"], "telegram_meta module unavailable")
            self.assertEqual(payload["task_id"], "T-7777")
            self.assertEqual(payload["project"], "bevox-mobile")
            self.assertEqual(payload["clarification_id"], "T-7777-clr-1")


if __name__ == "__main__":
    unittest.main()
