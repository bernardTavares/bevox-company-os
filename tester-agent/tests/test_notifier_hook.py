"""Tests for tester-agent → dispatcher notifier hook (Telegram terminal events).

Cobertura:
- Import do dispatcher notifier funciona (path injection OK)
- `_build_notifier_context` constrói shape esperado
- send_task_event é chamado com outcome correto por decision branch

Spec: bevox-knowledge/35_specs/openclaw/2026-04-29-dispatcher-notifier-tester-decision-and-capability-gating.md
"""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib import lifecycle as tester_lifecycle


class TestNotifierImport(unittest.TestCase):
    def test_dispatcher_notifier_imported(self):
        """Path injection no top do lifecycle.py expõe dispatcher.lib.notifier."""
        self.assertIsNotNone(tester_lifecycle.dispatcher_notifier)
        self.assertTrue(hasattr(tester_lifecycle.dispatcher_notifier, "send_task_event"))


class TestBuildNotifierContext(unittest.TestCase):
    def test_shape(self):
        task = {
            "id": "T-0001",
            "project": "bevox-site",
            "title": "Some task title",
        }
        log_path = Path("/tmp/T-0001.log")
        ctx = tester_lifecycle._build_notifier_context(task, log_path)
        self.assertEqual(ctx["project"], "bevox-site")
        self.assertEqual(ctx["title"], "Some task title")
        self.assertEqual(ctx["log_path"], "/tmp/T-0001.log")

    def test_missing_fields_use_fallback(self):
        ctx = tester_lifecycle._build_notifier_context({}, Path("/tmp/x.log"))
        self.assertEqual(ctx["project"], "?")
        self.assertEqual(ctx["title"], "?")


class TestNotifierHookOutcomeMapping(unittest.TestCase):
    """Verifica que cada decision do tester aciona o outcome correto.

    Mocka o pipeline inteiro acima do hook e captura a chamada ao notifier.
    """

    def _run_with_decision(self, decision_value, raw_checks):
        """Helper: invoca process_test_run com pipeline mockado e captura notifier call."""
        task = {
            "id": "T-0900",
            "project": "bevox-site",
            "title": "test task",
            "dispatch_payload": {
                "acceptance_criteria": ["AC1"],
            },
        }
        ctx = {
            "task": task,
            "acceptance_criteria": ["AC1"],
        }

        with patch.object(tester_lifecycle.context_loader,
                          "build_test_context", return_value=ctx), \
             patch.object(tester_lifecycle.context_loader,
                          "execution_log_path", return_value=Path("/tmp/T-0900.log")), \
             patch.object(tester_lifecycle.prechecks, "run_prechecks",
                          return_value={"passed": True, "details": {}, "failure_reason": ""}), \
             patch.object(tester_lifecycle, "_aggregate",
                          return_value={"overall": "x", "decision": decision_value}), \
             patch.object(tester_lifecycle, "_build_decision_reason",
                          return_value="reason xyz"), \
             patch.object(tester_lifecycle.checker_lib, "check_ac",
                          return_value={
                              "status": raw_checks[0]["status"],
                              "evidence": raw_checks[0].get("evidence", ""),
                              "sources": raw_checks[0].get("sources", []),
                              "structural_concern": "",
                              "raw_response": "",
                              "drafter_model": "test",
                          }), \
             patch.object(tester_lifecycle.safety, "enforce_safety",
                          return_value={
                              "effective_status": raw_checks[0]["status"],
                              "downgrade_reason": "",
                              "effective_structural_concern": "",
                              "valid_sources": [],
                              "invalid_sources": [],
                          }), \
             patch.object(tester_lifecycle.store, "next_test_run_seq", return_value=1), \
             patch.object(tester_lifecycle.store, "make_test_run_id",
                          return_value="T-0900-tr-1"), \
             patch.object(tester_lifecycle.store, "now_iso", return_value="2026-04-29T00:00:00Z"), \
             patch.object(tester_lifecycle.store, "write_test_run",
                          return_value=Path("/tmp/T-0900-tr-1.json")), \
             patch.object(tester_lifecycle, "move_to_done"), \
             patch.object(tester_lifecycle, "move_to_in_progress"), \
             patch.object(tester_lifecycle, "block"), \
             patch.object(tester_lifecycle, "merge_test_result"), \
             patch.object(tester_lifecycle, "_build_merge_fields", return_value={}), \
             patch.object(tester_lifecycle, "_write_escalation_md"), \
             patch.object(tester_lifecycle, "dispatcher_notifier") as mock_notif:
            mock_notif.send_task_event = MagicMock()
            tester_lifecycle.run_check("T-0900")
            return mock_notif.send_task_event

    def test_done_decision_emits_passed(self):
        send = self._run_with_decision(
            "done", [{"status": "pass", "ac": "AC1"}],
        )
        send.assert_called_once()
        args, kwargs = send.call_args
        self.assertEqual(args[0], "T-0900")
        self.assertEqual(args[1], "passed")
        self.assertIn("test_run_id", kwargs["context"])

    def test_failed_decision_emits_failed_test(self):
        send = self._run_with_decision(
            "in_progress_test_failed", [{"status": "fail", "ac": "AC1"}],
        )
        send.assert_called_once()
        args, kwargs = send.call_args
        self.assertEqual(args[1], "failed_test")
        self.assertEqual(kwargs["context"]["first_failed_ac"], "AC1")
        self.assertIn("test_run_path", kwargs["context"])

    def test_inconclusive_decision_emits_inconclusive(self):
        send = self._run_with_decision(
            "in_progress_test_inconclusive", [{"status": "inconclusive", "ac": "AC1"}],
        )
        send.assert_called_once()
        args, kwargs = send.call_args
        self.assertEqual(args[1], "inconclusive")
        self.assertIn("decision_reason", kwargs["context"])
        self.assertIn("test_run_path", kwargs["context"])

    def test_proposed_rejected_does_not_emit(self):
        """Rejection escreve escalation file mas não notifica Telegram."""
        send = self._run_with_decision(
            "proposed_rejected", [{"status": "pass", "ac": "AC1"}],
        )
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
