"""Tests poller: pre-filter, fast-fail, dedup."""
import unittest

from lib import poller


def _task(task_id="T-1", status="blocked", blocked=True,
          blocked_reason="clarification_required: ...",
          dispatch_payload=None):
    return {
        "id": task_id,
        "status": status,
        "blocked": blocked,
        "blocked_reason": blocked_reason,
        "dispatch_payload": dispatch_payload if dispatch_payload is not None else {
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["ac1"],
        },
    }


class TestPrefilter(unittest.TestCase):
    def test_skip_when_not_blocked(self):
        t = _task(blocked=False)
        skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "not_blocked")

    def test_skip_when_reason_is_execution_failed(self):
        t = _task(blocked_reason="execution_failed: exit 1")
        skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "blocked_reason_not_clarification")

    def test_skip_when_reason_is_test_failed(self):
        t = _task(blocked_reason="test_failed: AC1 nao passou")
        skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "blocked_reason_not_clarification")

    def test_keep_when_clarification_required(self):
        t = _task(blocked_reason="clarification_required: qual endpoint?")
        skip, reason, _ = poller.prefilter(t)
        self.assertFalse(skip)


class TestPrefilterAlreadyPending(unittest.TestCase):
    def test_skip_when_question_exists_without_answer(self):
        import tempfile, os
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            qdir = Path(d) / "questions"
            adir = Path(d) / "answers"
            qdir.mkdir()
            adir.mkdir()
            (qdir / "T-1-clr-1.md").write_text("q")
            with patch("lib.poller.store.QUESTIONS_DIR", qdir), \
                 patch("lib.poller.store.ANSWERS_DIR", adir):
                t = _task()
                skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "already_pending")

    def test_continue_when_answer_exists(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            qdir = Path(d) / "questions"
            adir = Path(d) / "answers"
            qdir.mkdir()
            adir.mkdir()
            (qdir / "T-1-clr-1.md").write_text("q")
            (adir / "T-1-clr-1.md").write_text("a")
            with patch("lib.poller.store.QUESTIONS_DIR", qdir), \
                 patch("lib.poller.store.ANSWERS_DIR", adir):
                t = _task()
                skip, reason, _ = poller.prefilter(t)
        self.assertFalse(skip)


class TestPrefilterBudget(unittest.TestCase):
    def test_skip_when_budget_exhausted_today(self):
        today = "2026-04-22"
        t = _task(dispatch_payload={
            "spec_ref": "x", "acceptance_criteria": ["a"],
            "clarification_budget": {"count_today": 3, "day": today, "limit": 3},
        })
        from unittest.mock import patch
        with patch("lib.poller._today_iso", return_value=today):
            skip, reason, _ = poller.prefilter(t)
        self.assertTrue(skip)
        self.assertEqual(reason, "budget_exhausted")

    def test_continue_when_budget_different_day(self):
        from unittest.mock import patch
        t = _task(dispatch_payload={
            "spec_ref": "x", "acceptance_criteria": ["a"],
            "clarification_budget": {"count_today": 3, "day": "2026-04-21", "limit": 3},
        })
        with patch("lib.poller._today_iso", return_value="2026-04-22"):
            skip, reason, _ = poller.prefilter(t)
        self.assertFalse(skip)


class TestPrefilterDedupHash(unittest.TestCase):
    def test_skip_when_hash_matches(self):
        q_hash = poller.compute_dedup_hash("T-1", "qual endpoint?",
                                           {"spec_ref":"x","acceptance_criteria":["a"]})
        t = _task(dispatch_payload={
            "spec_ref": "x", "acceptance_criteria": ["a"],
            "clarification_dedup_hash_last": q_hash,
        })
        skip, reason, _ = poller.prefilter(t, proposed_question="qual endpoint?")
        self.assertTrue(skip)
        self.assertEqual(reason, "dedup_hash_match")


class TestFastFail(unittest.TestCase):
    def test_fast_fail_when_spec_ref_empty(self):
        t = _task(dispatch_payload={"spec_ref": "", "acceptance_criteria": ["a"]})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertTrue(fail)
        self.assertIn("spec_ref", missing)

    def test_fast_fail_when_ac_empty(self):
        t = _task(dispatch_payload={"spec_ref": "x", "acceptance_criteria": []})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertTrue(fail)
        self.assertIn("acceptance_criteria", missing)

    def test_fast_fail_when_both_missing(self):
        t = _task(dispatch_payload={})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertTrue(fail)
        self.assertIn("spec_ref", missing)
        self.assertIn("acceptance_criteria", missing)

    def test_pass_when_both_populated(self):
        t = _task(dispatch_payload={"spec_ref": "x", "acceptance_criteria": ["a"]})
        fail, missing = poller.is_payload_incomplete(t)
        self.assertFalse(fail)
        self.assertEqual(missing, [])


class TestLocksAndKillSwitch(unittest.TestCase):
    def test_lock_contention_returns_none(self):
        import tempfile, fcntl
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            lock_path = Path(d) / "poll.lock"
            # Segurando um lock externo
            with open(lock_path, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch("lib.poller.store.POLL_LOCK", lock_path):
                    got = poller.try_acquire_lock()
                self.assertIsNone(got)

    def test_killswitch_active(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            kill = Path(d) / "poll.disabled"
            kill.touch()
            with patch("lib.poller.store.POLL_DISABLED", kill):
                self.assertTrue(poller.killswitch_active())

    def test_killswitch_absent(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            kill = Path(d) / "poll.disabled"
            with patch("lib.poller.store.POLL_DISABLED", kill):
                self.assertFalse(poller.killswitch_active())


class TestRunTickDryRun(unittest.TestCase):
    def test_dry_run_no_mutations(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            jsonl = root / "poll.jsonl"
            with patch("lib.poller.store.POLL_JSONL", jsonl), \
                 patch("lib.poller.store.POLL_LOCK", root / "poll.lock"), \
                 patch("lib.poller.store.POLL_DISABLED", root / "poll.disabled"), \
                 patch("lib.poller.store.QUESTIONS_DIR", root / "questions"), \
                 patch("lib.poller.store.ANSWERS_DIR", root / "answers"), \
                 patch("lib.poller._list_blocked_tasks", return_value=[
                     _task("T-A", dispatch_payload={"spec_ref":"", "acceptance_criteria":[]}),
                     _task("T-B"),
                 ]):
                result = poller.run_tick(once=True, dry_run=True)
        # Dry-run não grava eventos no JSONL
        self.assertFalse(jsonl.exists() and jsonl.stat().st_size > 0)
        self.assertEqual(result["tasks_scanned"], 2)
        self.assertTrue(result["dry_run"])


if __name__ == "__main__":
    unittest.main()
