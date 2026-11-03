"""Unit tests for UBN block_scanner — 3 critérios + dedup.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3
"""
import unittest
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from lib import block_scanner


class TestCriterionBlocked(unittest.TestCase):
    def test_returns_blocked_tasks_with_block_session_key(self):
        state = {
            "tasks": [
                {"id": "T-0001", "blocked": True,
                 "blocked_at": "2026-04-30T12:00:00Z",
                 "blocked_reason": "test_failed: AC1",
                 "project": "bevox-site"},
                {"id": "T-0002", "blocked": False, "project": "bevox-site"},
            ]
        }
        candidates = block_scanner.candidates_blocked(state)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0001")
        self.assertEqual(candidates[0].criterion, "blocked")
        self.assertEqual(candidates[0].block_session_key, "2026-04-30T12:00:00Z")
        self.assertEqual(candidates[0].block_reason, "test_failed: AC1")
        self.assertEqual(candidates[0].project, "bevox-site")

    def test_empty_state_returns_empty_list(self):
        self.assertEqual(block_scanner.candidates_blocked({"tasks": []}), [])

    def test_blocked_without_blocked_at_uses_unknown_key(self):
        """Defensivo — task com blocked=true mas sem blocked_at."""
        state = {"tasks": [
            {"id": "T-0003", "blocked": True, "blocked_reason": "x", "project": "p"}
        ]}
        candidates = block_scanner.candidates_blocked(state)
        self.assertEqual(len(candidates), 1)
        self.assertIsNone(candidates[0].block_session_key)


class TestCriterionProposedRejected(unittest.TestCase):
    def setUp(self):
        import tempfile, shutil
        from pathlib import Path
        self.tmp = tempfile.mkdtemp()
        self.tmp_path = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_escalation(self, task_id, test_run_id, decision="proposed_rejected"):
        from pathlib import Path
        path = self.tmp_path / f"{test_run_id}.md"
        path.write_text(f"""---
test_run_id: {test_run_id}
task_id: {task_id}
decision: {decision}
structural_concern: spec_inconsistent
generated_at: 2026-04-30T12:00:00Z
---
body
""")
        return path

    def test_detects_proposed_rejected_in_24h_window(self):
        from unittest.mock import patch
        self._write_escalation("T-0010", "T-0010-tr-1")
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            with patch.object(block_scanner, "_lookup_project_from_kanban", return_value="bevox-site"):
                candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0010")
        self.assertEqual(candidates[0].criterion, "proposed_rejected")
        self.assertEqual(candidates[0].block_session_key, "T-0010-tr-1")
        self.assertIn("spec_inconsistent", candidates[0].block_reason)

    def test_skips_files_older_than_24h(self):
        import os
        from unittest.mock import patch
        path = self._write_escalation("T-0011", "T-0011-tr-1")
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
        os.utime(path, (old, old))
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(candidates, [])

    def test_skips_decisions_other_than_proposed_rejected(self):
        from unittest.mock import patch
        self._write_escalation("T-0012", "T-0012-tr-1", decision="done")
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(candidates, [])

    def test_skips_legacy_files_without_frontmatter(self):
        from unittest.mock import patch
        (self.tmp_path / "T-0013-tr-1.md").write_text("# legacy file")
        with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", self.tmp_path):
            candidates = block_scanner.candidates_proposed_rejected()
        self.assertEqual(candidates, [])


class TestCriterionStuckInTesting(unittest.TestCase):
    def _state_with_task(self, task_id, status, updated_minutes_ago,
                         test_result=None, blocked=False):
        updated = (datetime.now(timezone.utc)
                   - timedelta(minutes=updated_minutes_ago)).isoformat().replace("+00:00", "Z")
        task = {
            "id": task_id, "status": status, "blocked": blocked,
            "updated_at": updated, "project": "bevox-site",
            "dispatch_payload": {"test_result": test_result or {}},
        }
        return {"tasks": [task]}

    def test_detects_task_in_testing_over_threshold(self):
        state = self._state_with_task("T-0020", "testing", updated_minutes_ago=45)
        candidates = block_scanner.candidates_stuck_testing(state)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0020")
        self.assertEqual(candidates[0].criterion, "stuck_in_testing")
        self.assertIn("stuck-in-testing", candidates[0].block_reason)

    def test_skips_task_below_threshold(self):
        state = self._state_with_task("T-0021", "testing", updated_minutes_ago=10)
        self.assertEqual(block_scanner.candidates_stuck_testing(state), [])

    def test_skips_blocked_task(self):
        state = self._state_with_task("T-0022", "testing", 45, blocked=True)
        self.assertEqual(block_scanner.candidates_stuck_testing(state), [])

    def test_excludes_inconclusive_within_backoff_window(self):
        """Task com last_test=inconclusive dentro de backoff window do reaper
        NÃO é stuck — está legitimamente esperando próxima invocação."""
        recent = (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat().replace("+00:00", "Z")
        # test_run_count=1 → backoff 30s. 20s < 30s → ainda em backoff.
        state = self._state_with_task("T-0023", "testing", 45, test_result={
            "last_test_overall": "inconclusive",
            "last_test_finished_at": recent,
            "test_run_count": 1,
        })
        self.assertEqual(block_scanner.candidates_stuck_testing(state), [])

    def test_includes_inconclusive_after_backoff_window(self):
        """Task com inconclusive ALÉM do backoff window vira stuck."""
        old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
        # test_run_count=1 → backoff 30s. 120s >> 30s → não está mais em backoff.
        state = self._state_with_task("T-0024", "testing", 45, test_result={
            "last_test_overall": "inconclusive",
            "last_test_finished_at": old,
            "test_run_count": 1,
        })
        candidates = block_scanner.candidates_stuck_testing(state)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].task_id, "T-0024")

    def test_threshold_env_var_override(self):
        state = self._state_with_task("T-0025", "testing", updated_minutes_ago=10)
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_TESTING_THRESHOLD_MIN": "5"}):
            candidates = block_scanner.candidates_stuck_testing(state)
        self.assertEqual(len(candidates), 1)


class TestDedup(unittest.TestCase):
    def setUp(self):
        import tempfile
        import shutil
        from pathlib import Path
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_existing_escalation(self, task_id, seq, block_session_key, status="open"):
        path = self.escalations_dir / f"{task_id}-blk-{seq}.md"
        path.write_text(f"""---
escalation_id: {task_id}-blk-{seq}
task_id: {task_id}
block_session_key: {block_session_key}
status: {status}
---
""")
        return path

    def test_dedup_returns_existing_when_session_key_matches(self):
        self._write_existing_escalation("T-0030", 1, "2026-04-30T10:00:00Z")
        candidate = block_scanner.Candidate(
            task_id="T-0030", criterion="blocked",
            block_session_key="2026-04-30T10:00:00Z",
            block_reason="x", project="p",
        )
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            existing = block_scanner.find_open_escalation(candidate)
        self.assertIsNotNone(existing)
        self.assertEqual(existing.name, "T-0030-blk-1.md")

    def test_dedup_returns_none_for_different_session_key(self):
        self._write_existing_escalation("T-0031", 1, "2026-04-30T10:00:00Z")
        candidate = block_scanner.Candidate(
            task_id="T-0031", criterion="blocked",
            block_session_key="2026-04-30T11:00:00Z",
            block_reason="x", project="p",
        )
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            existing = block_scanner.find_open_escalation(candidate)
        self.assertIsNone(existing)

    def test_dedup_ignores_resolved_escalations(self):
        self._write_existing_escalation("T-0032", 1, "key", status="resolved")
        candidate = block_scanner.Candidate(
            task_id="T-0032", criterion="blocked",
            block_session_key="key", block_reason="x", project="p",
        )
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            existing = block_scanner.find_open_escalation(candidate)
        self.assertIsNone(existing)

    def test_next_seq_increments(self):
        self._write_existing_escalation("T-0033", 1, "key1", status="resolved")
        self._write_existing_escalation("T-0033", 2, "key2", status="resolved")
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            seq = block_scanner.next_escalation_seq("T-0033")
        self.assertEqual(seq, 3)


class TestScanAllDedup(unittest.TestCase):
    def test_scan_all_filters_existing_open_escalations(self):
        import tempfile
        import shutil
        from pathlib import Path
        tmp = tempfile.mkdtemp()
        try:
            esc_dir = Path(tmp)
            (esc_dir / "T-0040-blk-1.md").write_text(
                "---\nstatus: open\nblock_session_key: existing-key\n---\n")
            state = {"tasks": [{
                "id": "T-0040", "blocked": True,
                "blocked_at": "existing-key",
                "blocked_reason": "x", "project": "p",
            }]}
            with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", esc_dir):
                with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", esc_dir):
                    candidates = block_scanner.scan_all(state)
            # Task tem escalation aberta com mesma key → filtrada
            self.assertEqual(candidates, [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_scan_all_dedup_in_tick_same_task(self):
        """Mesma task hit por 2 critérios → retorna 1 candidate."""
        import tempfile
        import shutil
        from pathlib import Path
        tmp = tempfile.mkdtemp()
        try:
            esc_dir = Path(tmp)
            old_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            state = {"tasks": [{
                "id": "T-0041", "status": "testing", "blocked": True,
                "blocked_at": "k1", "blocked_reason": "x",
                "project": "p", "updated_at": old_iso,
                "dispatch_payload": {"test_result": {}},
            }]}
            with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", esc_dir):
                with patch.object(block_scanner, "TESTER_ESCALATIONS_DIR", esc_dir):
                    candidates = block_scanner.scan_all(state)
            # Uma task pode hit blocked + stuck (se status=testing). Esperado: 1 candidate.
            # Mas como blocked check filtra status=blocked=True (que pula stuck check),
            # devemos receber 1 candidate de criterion blocked.
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].criterion, "blocked")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestCandidatesStuckReady(unittest.TestCase):
    """F4: task ready em sprint current sem dispatch há > threshold_min."""

    def _state_with(self, tasks, sprints):
        return {"tasks": tasks, "sprints": sprints}

    def test_ready_in_current_sprint_old_returns_candidate(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=45)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{
                "id": "T-0165", "status": "ready", "project": "bevox-site",
                "sprint_id": "sprint-35", "updated_at": old_ts,
            }],
            sprints=[{"id": "sprint-35", "project": "bevox-site", "state": "current"}],
        )
        out = candidates_stuck_ready(state)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].task_id, "T-0165")
        self.assertEqual(out[0].criterion, "stuck_in_ready")
        self.assertEqual(out[0].project, "bevox-site")

    def test_ready_recent_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": recent}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_ready_in_non_current_sprint_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "old-sprint", "updated_at": old}],
            sprints=[{"id": "current-sprint", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_in_progress_status_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "in_progress", "project": "p",
                    "sprint_id": "s1", "updated_at": old}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_threshold_env_override(self):
        import os
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": ts}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        from unittest.mock import patch
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN": "5"}):
            self.assertEqual(len(candidates_stuck_ready(state)), 1)
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN": "30"}):
            self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_kill_switch_zero_disables(self):
        import os
        from lib.block_scanner import candidates_stuck_ready
        from datetime import datetime, timezone, timedelta
        ts = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": ts}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        from unittest.mock import patch
        with patch.dict(os.environ, {"OPENCLAW_REAPER_STUCK_READY_THRESHOLD_MIN": "0"}):
            self.assertEqual(len(candidates_stuck_ready(state)), 0)

    def test_corrupted_updated_at_skipped(self):
        from lib.block_scanner import candidates_stuck_ready
        state = self._state_with(
            tasks=[{"id": "T-0165", "status": "ready", "project": "p",
                    "sprint_id": "s1", "updated_at": "not-a-date"}],
            sprints=[{"id": "s1", "project": "p", "state": "current"}],
        )
        self.assertEqual(len(candidates_stuck_ready(state)), 0)


if __name__ == "__main__":
    unittest.main()


class TestFindUndispatchedOpen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_esc(self, task_id, seq, **frontmatter_overrides):
        defaults = {
            "task_id": task_id,
            "project": "bevox-site",
            "criterion": "blocked",
            "block_session_key": "key1",
            "block_reason": "test_failed",
            "status": "open",
            "dispatched_at": "null",
            "telegram_message_id": "null",
        }
        defaults.update(frontmatter_overrides)
        path = self.escalations_dir / f"{task_id}-blk-{seq}.md"
        fm = "\n".join(f"{k}: {v}" for k, v in defaults.items())
        path.write_text(f"---\n{fm}\n---\nbody\n")
        return path

    def test_finds_open_undispatched_within_24h(self):
        self._write_esc("T-0070", 1)
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            results = block_scanner.find_undispatched_open_escalations()
        self.assertEqual(len(results), 1)
        path, frontmatter = results[0]
        self.assertEqual(frontmatter["task_id"], "T-0070")

    def test_skips_resolved_escalations(self):
        self._write_esc("T-0071", 1, status="resolved")
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            results = block_scanner.find_undispatched_open_escalations()
        self.assertEqual(results, [])

    def test_skips_already_dispatched(self):
        self._write_esc("T-0072", 1, dispatched_at="2026-05-04T10:00:00Z",
                        telegram_message_id="123")
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            results = block_scanner.find_undispatched_open_escalations()
        self.assertEqual(results, [])

    def test_skips_files_older_than_max_age(self):
        path = self._write_esc("T-0073", 1)
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).timestamp()
        os.utime(path, (old, old))
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            results = block_scanner.find_undispatched_open_escalations(max_age_hours=24)
        self.assertEqual(results, [])

    def test_max_age_hours_configurable(self):
        path = self._write_esc("T-0074", 1)
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
        os.utime(path, (old, old))
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            results = block_scanner.find_undispatched_open_escalations(max_age_hours=1)
        self.assertEqual(results, [])  # 2h > 1h cutoff
        with patch.object(block_scanner, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            results = block_scanner.find_undispatched_open_escalations(max_age_hours=3)
        self.assertEqual(len(results), 1)
