"""Test F3.2: reaper detecta executors legacy (sem RuntimeMaxSec) vivos > 12h.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F3.2
"""
import unittest
from unittest.mock import patch, MagicMock


class TestExecutorLegacyDetection(unittest.TestCase):
    def test_unit_with_runtime_max_set_skipped(self):
        """RuntimeMaxUSec != infinity → systemd cuida, skip."""
        from lib.reaper import _is_legacy_executor
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "43200000000\n", "returncode": 0,
            })()
            self.assertFalse(_is_legacy_executor("claude-task-T-9001.service"))

    def test_unit_with_infinity_is_legacy(self):
        from lib.reaper import _is_legacy_executor
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": "infinity\n", "returncode": 0,
            })()
            self.assertTrue(_is_legacy_executor("claude-task-T-0161.service"))

    def test_subprocess_failure_returns_false(self):
        from lib.reaper import _is_legacy_executor
        with patch("subprocess.run", side_effect=OSError):
            self.assertFalse(_is_legacy_executor("invalid"))


class TestExecutorAge(unittest.TestCase):
    def test_unit_age_hours_from_active_enter_timestamp(self):
        from lib.reaper import _executor_age_hours
        with patch("subprocess.run") as mock_run:
            # ActiveEnterTimestamp epoch in usec (systemd format)
            from datetime import datetime, timezone, timedelta
            ts = (datetime.now(timezone.utc) - timedelta(hours=14)).timestamp() * 1_000_000
            mock_run.return_value = type("R", (), {
                "stdout": f"{int(ts)}\n", "returncode": 0,
            })()
            age = _executor_age_hours("claude-task-T-9001.service")
            self.assertGreater(age, 13.5)
            self.assertLess(age, 14.5)

    def test_unit_age_hours_from_systemd_display_format(self):
        """Systemd output: 'Wed 2026-04-29 19:16:00 -03' (weekday + truncated tz)."""
        from lib.reaper import _executor_age_hours
        from datetime import datetime, timezone, timedelta
        # Build a real timestamp 5h ago in UTC, format as systemd display
        five_hours_ago = datetime.now(timezone.utc) - timedelta(hours=5)
        # Systemd emits in local tz with truncated offset. Simulate "-03":
        # 5h ago in UTC = 2h ago "in -03 tz". Use UTC representation but offset -03.
        local_dt = five_hours_ago.astimezone(timezone(timedelta(hours=-3)))
        ts_display = f"Wed {local_dt.strftime('%Y-%m-%d %H:%M:%S')} -03"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {
                "stdout": ts_display + "\n", "returncode": 0,
            })()
            age = _executor_age_hours("claude-task-T-0161.service")
            self.assertGreater(age, 4.5)
            self.assertLess(age, 5.5)


class TestExecutorLegacyReaperStage(unittest.TestCase):
    def test_legacy_unit_over_12h_killed(self):
        from lib import reaper
        with patch("lib.reaper._list_active_executor_units",
                   return_value=["claude-task-T-0161-old.service"]):
            with patch("lib.reaper._is_legacy_executor", return_value=True):
                with patch("lib.reaper._executor_age_hours", return_value=120.0):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = type("R", (), {"returncode": 0})()
                        with patch("lib.reaper.append_audit") as mock_audit:
                            stats = reaper._executor_legacy_reaper_stage()
                            self.assertEqual(stats.get("killed", 0), 1)
                            mock_audit.assert_called_once()
                            event = mock_audit.call_args[0][0]
                            self.assertEqual(event["type"], "executor_killed_legacy")

    def test_unit_under_12h_not_killed(self):
        from lib import reaper
        with patch("lib.reaper._list_active_executor_units",
                   return_value=["claude-task-recent.service"]):
            with patch("lib.reaper._is_legacy_executor", return_value=True):
                with patch("lib.reaper._executor_age_hours", return_value=2.0):
                    with patch("subprocess.run") as mock_run:
                        with patch("lib.reaper.append_audit"):
                            stats = reaper._executor_legacy_reaper_stage()
                            self.assertEqual(stats.get("killed", 0), 0)
                            mock_run.assert_not_called()

    def test_non_legacy_unit_skipped(self):
        from lib import reaper
        with patch("lib.reaper._list_active_executor_units",
                   return_value=["claude-task-modern.service"]):
            with patch("lib.reaper._is_legacy_executor", return_value=False):
                with patch("lib.reaper._executor_age_hours", return_value=120.0):
                    with patch("subprocess.run") as mock_run:
                        stats = reaper._executor_legacy_reaper_stage()
                        self.assertEqual(stats.get("killed", 0), 0)
                        mock_run.assert_not_called()

    def test_kill_switch_disables_stage(self):
        import os
        from lib import reaper
        with patch.dict(os.environ, {"OPENCLAW_REAPER_EXECUTOR_LEGACY": "0"}):
            stats = reaper._executor_legacy_reaper_stage()
            self.assertEqual(stats.get("skipped_disabled", 0), 1)


if __name__ == "__main__":
    unittest.main()
