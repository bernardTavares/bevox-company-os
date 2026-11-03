"""Testes dispatcher-agent notifier — Telegram task_done/task_failed."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import notifier


class TestSendTaskEvent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jsonl = Path(self.tmp) / "notifier.jsonl"
        self.patcher = patch.object(notifier, "JSONL_PATH", self.jsonl)
        self.patcher.start()
        # Isola dos projects-meta.json reais — testes de formato verificam
        # o triple env, não a resolução per-project.
        import sys
        if "telegram_meta" in sys.modules:
            self.tm_patcher = patch.object(
                sys.modules["telegram_meta"], "resolve_telegram_target",
                lambda *a, **kw: None,
            )
            self.tm_patcher.start()
        else:
            self.tm_patcher = None

    def tearDown(self):
        self.patcher.stop()
        if self.tm_patcher is not None:
            self.tm_patcher.stop()
        import shutil
        shutil.rmtree(self.tmp)

    def test_env_vars_missing_is_noop(self):
        """Sem env vars → retorna sem HTTP call + jsonl event skipped."""
        ctx = {"project": "bevox-mobile", "title": "test", "log_path": "/tmp/x"}
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(notifier, "_send_http") as mock_http:
                notifier.send_task_event("T-0001", "passed", context=ctx)
                mock_http.assert_not_called()
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "skipped:env_missing")
        self.assertEqual(events[0]["task_id"], "T-0001")

    def test_env_thread_not_int_is_noop(self):
        """THREAD_ID não-numérico → skipped:env_invalid."""
        ctx = {"project": "p", "title": "t", "log_path": "/tmp/x"}
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-100",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "NOT_INT",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(notifier, "_send_http") as mock_http:
                notifier.send_task_event("T-0001", "passed", context=ctx)
                mock_http.assert_not_called()
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "skipped:env_invalid")

    def test_unknown_outcome_skipped(self):
        """Outcome desconhecido → skipped:unknown_outcome, sem HTTP."""
        ctx = {"project": "p", "title": "t", "log_path": "/tmp/x"}
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(notifier, "_send_http") as mock_http:
                notifier.send_task_event("T-0001", "bogus", context=ctx)
                mock_http.assert_not_called()
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "skipped:unknown_outcome")


    def _full_env(self):
        return {
            "TELEGRAM_BOT_TOKEN": "tok-abc",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-1001234567890",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "42",
        }

    def test_moved_to_testing_message_format(self):
        ctx = {
            "project": "bevox-mobile",
            "title": "Implementar feature X",
            "log_path": f"{Path.home()}/.openclaw/dispatcher-agent/executions/T-0001.log",
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 99})) as mock_http:
                notifier.send_task_event("T-0001", "moved_to_testing", context=ctx)
                self.assertEqual(mock_http.call_count, 1)
                url, payload = mock_http.call_args.args
                self.assertIn("/bottok-abc/sendMessage", url)
                body = json.loads(payload.decode("utf-8"))
                self.assertEqual(body["chat_id"], "-1001234567890")
                self.assertEqual(body["message_thread_id"], 42)
                self.assertIn("🟡", body["text"])
                self.assertIn("moved to testing", body["text"])
                self.assertIn("T-0001", body["text"])
                self.assertIn("bevox-mobile", body["text"])
                self.assertIn("Implementar feature X", body["text"])
                self.assertIn("T-0001.log", body["text"])

    def test_moved_to_testing_suppressed_by_env(self):
        ctx = {"project": "p", "title": "t", "log_path": "/tmp/x"}
        env = {**self._full_env(),
               "OPENCLAW_DISPATCHER_NOTIFIER_SUPPRESS_MOVED_TO_TESTING": "1"}
        with patch.dict(os.environ, env, clear=True):
            with patch.object(notifier, "_send_http") as mock_http:
                notifier.send_task_event("T-0099", "moved_to_testing", context=ctx)
                mock_http.assert_not_called()
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "skipped:suppressed")

    def test_failed_execution_message_format(self):
        ctx = {
            "project": "bevox-backend",
            "title": "Fix bug Y",
            "log_path": "/tmp/T-0002.log",
            "failure_reason": "ImportError: no module foo",
            "exit_code": 1,
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 100})) as mock_http:
                notifier.send_task_event("T-0002", "failed_execution", context=ctx)
                self.assertEqual(mock_http.call_count, 1)
                body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                self.assertEqual(body["message_thread_id"], 42)
                self.assertIn("❌", body["text"])
                self.assertIn("execution failed", body["text"])
                self.assertIn("T-0002", body["text"])
                self.assertIn("bevox-backend", body["text"])
                self.assertIn("Fix bug Y", body["text"])
                self.assertIn("ImportError", body["text"])
                self.assertIn("exit: 1", body["text"])

    def test_passed_message_format(self):
        ctx = {
            "project": "bevox-site",
            "title": "T pass",
            "log_path": "/tmp/T-0010.log",
            "test_run_id": "T-0010-tr-1",
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 200})) as mock_http:
                notifier.send_task_event("T-0010", "passed", context=ctx)
                self.assertEqual(mock_http.call_count, 1)
                body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                self.assertIn("✅", body["text"])
                self.assertIn("T-0010 passed", body["text"])
                self.assertIn("T-0010-tr-1", body["text"])

    def test_failed_test_message_format(self):
        ctx = {
            "project": "bevox-site",
            "title": "Build container",
            "log_path": "/tmp/T-0011.log",
            "first_failed_ac": "Imagem builda corretamente",
            "test_run_path": "/tmp/T-0011-tr-1.json",
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 201})) as mock_http:
                notifier.send_task_event("T-0011", "failed_test", context=ctx)
                self.assertEqual(mock_http.call_count, 1)
                body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                self.assertIn("❌", body["text"])
                self.assertIn("failed test", body["text"])
                self.assertIn("Imagem builda corretamente", body["text"])
                self.assertIn("/tmp/T-0011-tr-1.json", body["text"])

    def test_inconclusive_message_format(self):
        ctx = {
            "project": "bevox-site",
            "title": "Dataset cena",
            "log_path": "/tmp/T-0012.log",
            "decision_reason": "1/3 AC inconclusive: timeout",
            "test_run_path": "/tmp/T-0012-tr-1.json",
        }
        with patch.dict(os.environ, self._full_env(), clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 202})) as mock_http:
                notifier.send_task_event("T-0012", "inconclusive", context=ctx)
                self.assertEqual(mock_http.call_count, 1)
                body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                self.assertIn("⚠️", body["text"])
                self.assertIn("inconclusive", body["text"])
                self.assertIn("timeout", body["text"])
                self.assertIn("/tmp/T-0012-tr-1.json", body["text"])

    def test_telegram_http_failure_swallowed(self):
        """urllib erro → função não raise, jsonl event 'failed:*'."""
        import urllib.error
        ctx = {"project": "p", "title": "t", "log_path": "/tmp/x"}
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-100",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "42",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("net down")):
                # Não deve levantar
                notifier.send_task_event("T-0003", "passed", context=ctx)
        events = [json.loads(l) for l in self.jsonl.read_text().splitlines()]
        last = events[-1]
        self.assertTrue(last["event"].startswith("failed:"))
        self.assertEqual(last["task_id"], "T-0003")

    def test_empty_context_uses_fallbacks(self):
        """context missing keys → message still sent with '?' placeholders."""
        env = {
            "TELEGRAM_BOT_TOKEN": "tok",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-100",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": "42",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(notifier, "_send_http", return_value=(True, {"message_id": 1})) as mock_http:
                notifier.send_task_event("T-0099", "moved_to_testing", context={})
                self.assertEqual(mock_http.call_count, 1)
                body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                self.assertIn("T-0099", body["text"])
                self.assertIn("project: ?", body["text"])
                self.assertIn("title: ?", body["text"])
                self.assertIn("log: ?", body["text"])


class TestPerProjectTopicLookup(unittest.TestCase):
    """Phase 4: prefer projects-meta.json telegram.topics.dispatcher."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.jsonl = Path(self.tmp) / "notifier.jsonl"
        self.patcher = patch.object(notifier, "JSONL_PATH", self.jsonl)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        import shutil
        shutil.rmtree(self.tmp)

    def _full_env(self, thread_id="42"):
        return {
            "TELEGRAM_BOT_TOKEN": "tok-abc",
            "OPENCLAW_DISPATCHER_TELEGRAM_CHAT_ID": "-1001234567890",
            "OPENCLAW_DISPATCHER_TELEGRAM_THREAD_ID": thread_id,
        }

    def test_send_task_event_uses_meta_target_when_present(self):
        """When projects-meta.json has dispatcher topic, that triple wins."""
        import sys
        ctx = {"project": "smoke-proj", "title": "x",
               "log_path": "/tmp/T-0001.log"}
        meta_target = ("tok-meta", "-1009999999999", 999)
        with patch.dict(os.environ, self._full_env(thread_id="1"), clear=True):
            with patch.object(sys.modules["telegram_meta"], "resolve_telegram_target",
                              lambda slug, topic: meta_target if topic == "dispatcher" else None):
                with patch.object(notifier, "_send_http",
                                  return_value=(True, {"message_id": 1})) as mock_http:
                    notifier.send_task_event("T-0001", "passed", context=ctx)
                    self.assertEqual(mock_http.call_count, 1)
                    body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                    self.assertEqual(body["message_thread_id"], 999)
                    self.assertEqual(body["chat_id"], "-1009999999999")
                    url = mock_http.call_args.args[0]
                    self.assertIn("/bottok-meta/sendMessage", url)

    def test_send_task_event_falls_back_to_env_when_meta_silent(self):
        """When meta returns None, env triple is used."""
        import sys
        ctx = {"project": "smoke-proj", "title": "x",
               "log_path": "/tmp/T-0002.log"}
        with patch.dict(os.environ, self._full_env(thread_id="42"), clear=True):
            with patch.object(sys.modules["telegram_meta"], "resolve_telegram_target",
                              lambda *a, **kw: None):
                with patch.object(notifier, "_send_http",
                                  return_value=(True, {"message_id": 1})) as mock_http:
                    notifier.send_task_event("T-0002", "passed", context=ctx)
                    self.assertEqual(mock_http.call_count, 1)
                    body = json.loads(mock_http.call_args.args[1].decode("utf-8"))
                    self.assertEqual(body["message_thread_id"], 42)
                    self.assertEqual(body["chat_id"], "-1001234567890")


if __name__ == "__main__":
    unittest.main()
