"""Tests for CAPABILITY_MISSING marker pre-scan in checker.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-29-dispatcher-notifier-tester-decision-and-capability-gating.md §5
"""
import unittest
from unittest.mock import patch

from lib import checker as checker_lib


class TestScanCapabilityMissing(unittest.TestCase):
    def test_no_marker_returns_none(self):
        log = "Task done. pnpm build OK. Tests pass.\n"
        self.assertIsNone(checker_lib._scan_capability_missing(log))

    def test_empty_log_returns_none(self):
        self.assertIsNone(checker_lib._scan_capability_missing(""))

    def test_marker_returns_capability_name(self):
        log = (
            "Began task.\n"
            "CAPABILITY_MISSING: docker_build\n"
            "continued with other ACs.\n"
        )
        self.assertEqual(
            checker_lib._scan_capability_missing(log),
            "docker_build",
        )

    def test_marker_with_whitespace_normalized(self):
        log = "  CAPABILITY_MISSING:   internet_egress  \n"
        self.assertEqual(
            checker_lib._scan_capability_missing(log),
            "internet_egress",
        )

    def test_first_marker_wins(self):
        log = (
            "CAPABILITY_MISSING: docker_build\n"
            "later: CAPABILITY_MISSING: gh_cli\n"
        )
        self.assertEqual(
            checker_lib._scan_capability_missing(log),
            "docker_build",
        )

    def test_marker_without_name_ignored(self):
        log = "CAPABILITY_MISSING:   \n"
        self.assertIsNone(checker_lib._scan_capability_missing(log))


class TestCheckAcShortCircuitsOnCapability(unittest.TestCase):
    def test_short_circuit_skips_drafter_call(self):
        """Quando log tem CAPABILITY_MISSING, check_ac não chama claude -p."""
        ctx = {
            "execution_log_tail": "CAPABILITY_MISSING: docker_build\n",
            "task": {"id": "T-0001"},
        }
        with patch.object(checker_lib.subprocess, "run") as mock_run:
            result = checker_lib.check_ac("Imagem builda", ctx)
            mock_run.assert_not_called()
        self.assertEqual(result["status"], "inconclusive")
        self.assertEqual(result["structural_concern"],
                         "capability_required:docker_build")
        self.assertIn("docker_build", result["evidence"])

    def test_no_marker_falls_through_to_drafter(self):
        """Sem marker, check_ac segue chamando claude -p (mockado)."""
        ctx = {
            "execution_log_tail": "Task done normally.",
            "task": {"id": "T-0001"},
            "execution_log_path": "/tmp/T-0001.log",
            "spec_refs_resolved": [],
            "files_relevant_resolved": [],
        }

        class FakeRun:
            returncode = 0
            stdout = '```json\n{"status": "pass", "evidence": "ok",' \
                    '"sources": ["/tmp/T-0001.log"], "structural_concern": ""}\n```'
            stderr = ""

        with patch.object(checker_lib.subprocess, "run", return_value=FakeRun()) as mock_run:
            result = checker_lib.check_ac("AC1", ctx)
            mock_run.assert_called_once()
        self.assertEqual(result["status"], "pass")


if __name__ == "__main__":
    unittest.main()
