"""Test enriched Telegram message para criterion=blocked + test_inconclusive.

Background: T-0168 + T-0165 ficaram blocked com block_reason truncado a 200
chars sem clareza de qual AC ficou inconclusive nem evidência. Bernard não
conseguia decidir pelo Telegram. Solução: detectar test_inconclusive e
enriquecer mensagem com per-AC status + evidence inline.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.escalation_dispatcher import _format_message, _find_latest_test_run
from lib.block_scanner import Candidate


class TestFormatMessageTestInconclusive(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def _write_test_run(self, task_id: str, checks: list, run_n: int = 1):
        path = self.tmpdir / f"{task_id}-tr-{run_n}.json"
        path.write_text(json.dumps({
            "test_run_id": f"{task_id}-tr-{run_n}",
            "task_id": task_id,
            "overall": "inconclusive",
            "decision": "in_progress_test_inconclusive",
            "checks": checks,
        }), encoding="utf-8")
        return path

    def _candidate(self, task_id="T-0168"):
        return Candidate(
            task_id=task_id,
            criterion="blocked",
            block_session_key="2026-05-04T14:22:46Z",
            block_reason="test_inconclusive: Log describes detailed implementation",
            project="bevox-site",
        )

    def test_test_inconclusive_message_lists_per_ac_status(self):
        self._write_test_run("T-0168", [
            {"ac": "AC1 description", "effective_status": "pass", "evidence": "ev1"},
            {"ac": "AC2 description", "effective_status": "pass", "evidence": "ev2"},
            {"ac": "AC3 description", "effective_status": "inconclusive",
             "evidence": "Log shows X but no behavioral validation"},
        ])
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        self.assertIn("BLOCKED — test inconclusive", msg)
        self.assertIn("ACs (1/3 inconclusive)", msg)
        self.assertIn("✅ AC1", msg)
        self.assertIn("✅ AC2", msg)
        self.assertIn("❓ AC3", msg)

    def test_test_inconclusive_includes_evidence_for_inconclusive_ac(self):
        self._write_test_run("T-0168", [
            {"ac": "AC1", "effective_status": "inconclusive",
             "evidence": "no behavioral output provided"},
        ])
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        self.assertIn("no behavioral output provided", msg)

    def test_test_inconclusive_omits_evidence_for_pass_ac(self):
        """Evidence só aparece para ACs inconclusive — ACs pass têm icon só."""
        self._write_test_run("T-0168", [
            {"ac": "AC1", "effective_status": "pass",
             "evidence": "long pass evidence should NOT appear in telegram"},
            {"ac": "AC2", "effective_status": "inconclusive",
             "evidence": "this should appear"},
        ])
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        self.assertNotIn("long pass evidence", msg)
        self.assertIn("this should appear", msg)

    def test_test_inconclusive_includes_unblock_actions_with_descriptions(self):
        self._write_test_run("T-0168", [
            {"ac": "AC1", "effective_status": "inconclusive", "evidence": "x"},
        ])
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        self.assertIn("/unblock T-0168 pass", msg)
        self.assertIn("/unblock T-0168 retry", msg)
        self.assertIn("/unblock T-0168 cancel", msg)
        self.assertIn("/unblock T-0168 answer", msg)
        # Descriptions present (not just bare commands)
        self.assertIn("se revisado e ok", msg)
        self.assertIn("re-roda executor", msg)

    def test_evidence_truncated_at_400_chars(self):
        long_ev = "x" * 1000
        self._write_test_run("T-0168", [
            {"ac": "AC1", "effective_status": "inconclusive", "evidence": long_ev},
        ])
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        self.assertIn("...", msg)
        # Sanity: total msg fits in Telegram limit (4096)
        self.assertLess(len(msg), 4096)

    def test_ac_text_truncated_at_90_chars(self):
        long_ac = "AC com texto muito muito longo " * 10
        self._write_test_run("T-0168", [
            {"ac": long_ac, "effective_status": "pass", "evidence": "x"},
        ])
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        # AC line length truncated
        for line in msg.splitlines():
            if "✅ AC1" in line:
                # account for "  ✅ AC1 " prefix (~10 chars) + truncated body (90)
                self.assertLess(len(line), 110)

    def test_falls_back_to_generic_message_when_no_test_run(self):
        """Sem test_run, usa formato legado."""
        # No file written
        with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", self.tmpdir):
            msg = _format_message(self._candidate(), "T-0168-blk-1")
        # Falls back to legacy: "blocked\nproject:" sem "BLOCKED —"
        self.assertNotIn("BLOCKED — test inconclusive", msg)
        self.assertIn("⚠️ T-0168 blocked", msg)
        self.assertIn("reason:", msg)

    def test_non_test_inconclusive_uses_legacy_format(self):
        """Outros critérios (stuck_in_testing, proposed_rejected) usam formato legado."""
        c = Candidate(
            task_id="T-0050",
            criterion="stuck_in_testing",
            block_session_key="x",
            block_reason="stuck-in-testing >30min",
            project="bevox-site",
        )
        msg = _format_message(c, "T-0050-blk-1")
        self.assertIn("⚠️ T-0050 blocked", msg)  # legacy format
        self.assertNotIn("BLOCKED — test inconclusive", msg)

    def test_blocked_criterion_with_non_test_reason_uses_legacy(self):
        """criterion=blocked mas block_reason não inicia com 'test_inconclusive:'
        usa formato legado."""
        c = Candidate(
            task_id="T-0070",
            criterion="blocked",
            block_session_key="x",
            block_reason="branch_checkout_failed: cannot fetch ref",
            project="bevox-site",
        )
        msg = _format_message(c, "T-0070-blk-1")
        self.assertIn("⚠️ T-0070 blocked", msg)
        self.assertNotIn("BLOCKED — test inconclusive", msg)


class TestFindLatestTestRun(unittest.TestCase):
    def test_returns_latest_by_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            (tmpdir / "T-0001-tr-1.json").write_text('{"x": 1}')
            (tmpdir / "T-0001-tr-2.json").write_text('{"x": 2}')
            # Touch tr-2 to ensure it's newer (mtime granularity)
            import os, time
            time.sleep(0.01)
            os.utime(tmpdir / "T-0001-tr-2.json", None)
            with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", tmpdir):
                result = _find_latest_test_run("T-0001")
            self.assertEqual(result["x"], 2)

    def test_returns_none_when_no_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", tmpdir):
                result = _find_latest_test_run("T-9999")
            self.assertIsNone(result)

    def test_returns_none_on_corrupt_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            (tmpdir / "T-0001-tr-1.json").write_text("not json{")
            with patch("lib.escalation_dispatcher.TESTER_RUNS_DIR", tmpdir):
                result = _find_latest_test_run("T-0001")
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
