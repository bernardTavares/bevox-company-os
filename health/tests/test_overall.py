"""Tests for run_check dispatcher + compute_overall."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runner


class TestRunCheckDispatcher(unittest.TestCase):
    def test_dispatches_systemd_active(self):
        with patch.object(runner, "check_systemd_active") as m:
            m.return_value = {"status": "up", "detail": "active"}
            runner.run_check({
                "check": {"type": "systemd_active", "unit": "foo.service"}
            })
            m.assert_called_once()

    def test_dispatches_http_url(self):
        with patch.object(runner, "check_http_url") as m:
            m.return_value = {"status": "up", "detail": "200"}
            runner.run_check({
                "check": {"type": "http_url", "url": "https://x"}
            })
            m.assert_called_once()

    def test_dispatches_file_freshness(self):
        with patch.object(runner, "check_file_freshness") as m:
            m.return_value = {"status": "up", "detail": "age 10s"}
            runner.run_check({
                "check": {"type": "file_freshness", "path": "/tmp/x", "max_age_sec": 60}
            })
            m.assert_called_once()

    def test_unknown_type_returns_unknown(self):
        result = runner.run_check({
            "check": {"type": "made_up"}
        })
        self.assertEqual(result["status"], "unknown")


class TestComputeOverall(unittest.TestCase):
    def _service(self, status, critical):
        return {"status": status, "critical": critical}

    def test_all_up_returns_ok(self):
        state = {
            "a": self._service("up", True),
            "b": self._service("up", False),
        }
        result = runner.compute_overall(state, {"a"})
        self.assertEqual(result["level"], "ok")

    def test_critical_down_returns_down(self):
        state = {
            "a": self._service("down", True),
            "b": self._service("up", False),
        }
        result = runner.compute_overall(state, {"a"})
        self.assertEqual(result["level"], "down")
        self.assertEqual(result["critical_not_up"], 1)

    def test_critical_unknown_returns_down(self):
        """Critical with unknown status is counted as not-up -> down."""
        state = {
            "a": self._service("unknown", True),
            "b": self._service("up", False),
        }
        result = runner.compute_overall(state, {"a"})
        self.assertEqual(result["level"], "down")
        self.assertEqual(result["critical_not_up"], 1)

    def test_critical_degraded_returns_down(self):
        state = {
            "a": self._service("degraded", True),
            "b": self._service("up", False),
        }
        result = runner.compute_overall(state, {"a"})
        self.assertEqual(result["level"], "down")
        self.assertEqual(result["critical_not_up"], 1)

    def test_non_critical_down_returns_degraded(self):
        state = {
            "a": self._service("up", True),
            "b": self._service("down", False),
        }
        result = runner.compute_overall(state, {"a"})
        self.assertEqual(result["level"], "degraded")
        self.assertEqual(result["critical_not_up"], 0)

    def test_non_critical_unknown_returns_degraded(self):
        state = {
            "a": self._service("up", True),
            "b": self._service("unknown", False),
        }
        result = runner.compute_overall(state, {"a"})
        self.assertEqual(result["level"], "degraded")

    def test_empty_state_returns_ok(self):
        result = runner.compute_overall({}, set())
        self.assertEqual(result["level"], "ok")
        self.assertEqual(result["services_total"], 0)

    def test_counters_correct(self):
        state = {
            "a": self._service("up", True),
            "b": self._service("up", True),
            "c": self._service("up", False),
            "d": self._service("degraded", False),
            "e": self._service("down", False),
            "f": self._service("unknown", False),
        }
        result = runner.compute_overall(state, {"a", "b"})
        self.assertEqual(result["critical_total"], 2)
        self.assertEqual(result["critical_up"], 2)
        self.assertEqual(result["critical_not_up"], 0)
        self.assertEqual(result["services_total"], 6)
        self.assertEqual(result["services_up"], 3)
        self.assertEqual(result["services_degraded"], 1)
        self.assertEqual(result["services_down"], 1)
        self.assertEqual(result["services_unknown"], 1)


class TestBuildState(unittest.TestCase):
    def test_build_state_complete_shape(self):
        services_state = {
            "foo": {
                "name": "Foo",
                "epic": "E0",
                "critical": True,
                "check_type": "systemd_active",
                "status": "up",
                "detail": "active",
                "checked_at": "2026-04-14T12:00:00.000Z",
                "duration_ms": 10,
            }
        }
        overall = {
            "level": "ok",
            "detail": None,
            "critical_total": 1,
            "critical_up": 1,
            "critical_not_up": 0,
            "services_total": 1,
            "services_up": 1,
            "services_degraded": 0,
            "services_down": 0,
            "services_unknown": 0,
        }
        state = runner.build_state(
            run_id="run_abc123",
            registry_version=1,
            services_state=services_state,
            overall=overall,
            total_duration_ms=50,
        )
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["run_id"], "run_abc123")
        self.assertEqual(state["registry_version"], 1)
        self.assertEqual(state["duration_ms"], 50)
        self.assertEqual(state["overall"], overall)
        self.assertEqual(state["services"], services_state)
        self.assertTrue(state["generated_at"].endswith("Z"))

    def test_build_unknown_state_on_registry_failure(self):
        state = runner.build_unknown_state(
            run_id="run_xyz",
            error="invalid YAML: foo",
        )
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["overall"]["level"], "unknown")
        self.assertEqual(state["overall"]["detail"], "invalid YAML: foo")
        self.assertEqual(state["services"], {})
        self.assertIsNone(state["overall"]["critical_total"])


class TestWriteStateAtomic(unittest.TestCase):
    def test_atomic_write_creates_file(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp()) / "state.json"
        state = {"schema_version": 1, "generated_at": "2026-04-14T12:00:00.000Z"}
        runner.write_state_atomic(state, tmp)
        self.assertTrue(tmp.exists())
        import json
        loaded = json.loads(tmp.read_text())
        self.assertEqual(loaded["schema_version"], 1)
        tmp.unlink()
        tmp.parent.rmdir()

    def test_atomic_write_overwrites(self):
        import tempfile
        tmp = Path(tempfile.mkdtemp()) / "state.json"
        tmp.write_text('{"old": true}')
        state = {"new": True}
        runner.write_state_atomic(state, tmp)
        import json
        loaded = json.loads(tmp.read_text())
        self.assertEqual(loaded, {"new": True})
        tmp.unlink()
        tmp.parent.rmdir()

    def test_atomic_write_uses_tempfile(self):
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())
        tmp = tmp_dir / "state.json"
        state = {"x": 1}
        runner.write_state_atomic(state, tmp)
        # No .tmp leftover after successful write
        leftover = list(tmp_dir.glob("*.tmp"))
        self.assertEqual(leftover, [])
        tmp.unlink()
        tmp_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
