"""Tests for alert-notifier.py — transition detection, formatting, state persistence."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "alert_notifier",
    str(Path(__file__).parent.parent / "alert-notifier.py"),
)
alert_notifier = importlib.util.module_from_spec(_spec)
sys.modules["alert_notifier"] = alert_notifier
_spec.loader.exec_module(alert_notifier)

detect_transition = alert_notifier.detect_transition
format_message = alert_notifier.format_message
load_alert_state = alert_notifier.load_alert_state
write_alert_state = alert_notifier.write_alert_state
run_check = alert_notifier.run_check


class TestDetectTransition(unittest.TestCase):
    def test_ok_to_ok(self):
        self.assertIsNone(detect_transition("ok", "ok"))

    def test_ok_to_degraded(self):
        self.assertEqual(detect_transition("ok", "degraded"), "alert")

    def test_ok_to_down(self):
        self.assertEqual(detect_transition("ok", "down"), "alert")

    def test_degraded_to_ok(self):
        self.assertEqual(detect_transition("degraded", "ok"), "recovery")

    def test_down_to_ok(self):
        self.assertEqual(detect_transition("down", "ok"), "recovery")

    def test_degraded_to_down(self):
        self.assertEqual(detect_transition("degraded", "down"), "alert")

    def test_down_to_degraded(self):
        self.assertEqual(detect_transition("down", "degraded"), "alert")

    def test_same_level_no_transition(self):
        self.assertIsNone(detect_transition("degraded", "degraded"))
        self.assertIsNone(detect_transition("down", "down"))

    def test_first_run_ok(self):
        self.assertIsNone(detect_transition(None, "ok"))

    def test_first_run_degraded(self):
        self.assertEqual(detect_transition(None, "degraded"), "alert")

    def test_first_run_down(self):
        self.assertEqual(detect_transition(None, "down"), "alert")


class TestFormatMessage(unittest.TestCase):
    def _make_state(self, level, services_up, services_total, affected=None):
        services = {}
        if affected:
            for s in affected:
                services[s] = {"status": "down"}
            for i in range(services_total - len(affected)):
                services[f"svc-ok-{i}"] = {"status": "up"}
        return {
            "overall": {"level": level, "services_up": services_up, "services_total": services_total},
            "services": services,
            "generated_at": "2026-04-16T03:02:15Z",
        }

    def test_alert_message(self):
        state = self._make_state("degraded", 13, 15, ["mission-control", "openclaw-gateway"])
        msg = format_message("alert", state)
        self.assertIn("⚠ Health degraded (13/15 up)", msg)
        self.assertIn("mission-control", msg)
        self.assertIn("openclaw-gateway", msg)

    def test_recovery_message(self):
        state = self._make_state("ok", 15, 15)
        msg = format_message("recovery", state)
        self.assertIn("✓ Health restored (15/15 up)", msg)

    def test_truncation_over_5(self):
        affected = [f"svc-{i}" for i in range(7)]
        state = self._make_state("down", 8, 15, affected)
        msg = format_message("alert", state)
        self.assertIn("+2 more", msg)


class TestAlertStatePersistence(unittest.TestCase):
    def test_first_run_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert-state.json"
            self.assertFalse(path.exists())
            state = load_alert_state(path)
            self.assertIsNone(state["last_level"])

    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert-state.json"
            write_alert_state(path, "degraded", True, "alert", "test msg")
            state = load_alert_state(path)
            self.assertEqual(state["last_level"], "degraded")
            self.assertIsNotNone(state["last_checked_at"])
            self.assertIsNotNone(state["last_alerted_at"])
            self.assertEqual(state["last_alert_type"], "alert")

    def test_heartbeat_updates_on_no_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alert-state.json"
            write_alert_state(path, "ok", False, None, None)
            s1 = load_alert_state(path)
            self.assertEqual(s1["last_level"], "ok")
            self.assertIsNotNone(s1["last_checked_at"])
            self.assertIsNone(s1["last_alerted_at"])


class TestRunCheckIntegration(unittest.TestCase):
    def test_first_run_ok_no_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            health = Path(tmp) / "state.json"
            alert = Path(tmp) / "alert-state.json"
            health.write_text(json.dumps({
                "overall": {"level": "ok", "services_up": 15, "services_total": 15},
                "services": {},
                "generated_at": "2026-04-16T03:00:00Z",
            }))

            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
                result = run_check(health, alert)

            self.assertEqual(result["action"], "none")
            self.assertFalse(result["sent"])
            state = load_alert_state(alert)
            self.assertEqual(state["last_level"], "ok")

    def test_first_run_degraded_attempts_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            health = Path(tmp) / "state.json"
            alert = Path(tmp) / "alert-state.json"
            health.write_text(json.dumps({
                "overall": {"level": "degraded", "services_up": 13, "services_total": 15},
                "services": {"mc": {"status": "down"}, "gw": {"status": "down"}},
                "generated_at": "2026-04-16T03:00:00Z",
            }))

            # No token = skip send but detect transition
            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
                result = run_check(health, alert)

            self.assertEqual(result["action"], "alert")
            self.assertFalse(result["sent"])  # no token

    def test_transition_ok_to_degraded_then_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            health = Path(tmp) / "state.json"
            alert = Path(tmp) / "alert-state.json"

            # Initialize with ok
            health.write_text(json.dumps({
                "overall": {"level": "ok", "services_up": 15, "services_total": 15},
                "services": {}, "generated_at": "T1",
            }))
            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
                run_check(health, alert)

            # Transition to degraded
            health.write_text(json.dumps({
                "overall": {"level": "degraded", "services_up": 14, "services_total": 15},
                "services": {"mc": {"status": "down"}}, "generated_at": "T2",
            }))
            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
                r2 = run_check(health, alert)
            self.assertEqual(r2["action"], "alert")

            # Stay degraded — no transition
            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
                r3 = run_check(health, alert)
            self.assertEqual(r3["action"], "none")

            # Recovery
            health.write_text(json.dumps({
                "overall": {"level": "ok", "services_up": 15, "services_total": 15},
                "services": {}, "generated_at": "T4",
            }))
            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
                r4 = run_check(health, alert)
            self.assertEqual(r4["action"], "recovery")


import os  # noqa: E402 — needed for mock.patch.dict


# ── E8/F5 wave 1 — Hardening alert integration ─────────────────────


class TestDetectTransitionSilentFirstRun(unittest.TestCase):
    """Spec §5.7: hardening first-time null → * does NOT alert (deploy noise).
    Health behavior unchanged (default silent_first_run=False).
    """

    def test_first_run_with_silent_returns_none_even_if_critical(self):
        self.assertIsNone(
            detect_transition(None, "critical", silent_first_run=True))

    def test_first_run_with_silent_returns_none_for_ok(self):
        self.assertIsNone(
            detect_transition(None, "ok", silent_first_run=True))

    def test_first_run_default_keeps_existing_behavior_alerts_on_critical(self):
        # health behavior preserved: first run + non-ok → alert
        self.assertEqual(detect_transition(None, "critical"), "alert")
        self.assertEqual(
            detect_transition(None, "critical", silent_first_run=False), "alert")


class TestFormatMessageWithPrefix(unittest.TestCase):
    """Spec §5.7: hardening alerts include [hardening] prefix."""

    def test_message_includes_hardening_prefix(self):
        state = {"overall": {"level": "critical", "items_total": 7,
                             "items_critical": 1, "items_ok": 6,
                             "items_degraded": 0, "items_unknown": 0,
                             "items_not_applicable": 0},
                 "items": [{"id": "ufw-active", "name": "UFW", "status": "critical",
                            "detail": "down"}],
                 "generated_at": "2026-04-19T10:00:00Z"}
        msg = format_message("alert", state, prefix="[hardening]")
        self.assertIn("[hardening]", msg)

    def test_default_no_prefix_for_health(self):
        state = {"overall": {"level": "critical", "services_total": 10,
                             "services_up": 9, "services_degraded": 0,
                             "services_down": 1, "services_unknown": 0},
                 "services": {}, "generated_at": "2026-04-19T10:00:00Z"}
        msg = format_message("alert", state)
        self.assertNotIn("[hardening]", msg)


class TestRunCheckHardeningIntegration(unittest.TestCase):
    """run_check evaluates BOTH health AND hardening states.

    alert-state.json gains last_hardening_level field.
    Hardening: silent_first_run; prefix [hardening].
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.health = self.tmp / "health.json"
        self.hardening = self.tmp / "hardening.json"
        self.alert = self.tmp / "alert-state.json"
        self.health.write_text(json.dumps({
            "overall": {"level": "ok", "services_up": 10, "services_total": 10,
                        "services_degraded": 0, "services_down": 0,
                        "services_unknown": 0, "critical_total": 0},
            "services": {}, "generated_at": "T1",
        }))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_hardening_missing_does_not_break_health_check(self):
        with mock.patch.dict(os.environ,
                             {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
            result = run_check(self.health, self.alert,
                               hardening_state_path=self.hardening)
        self.assertIn("action", result)
        st = json.loads(self.alert.read_text())
        self.assertEqual(st["last_level"], "ok")

    def test_hardening_first_scan_silent_no_alert(self):
        self.hardening.write_text(json.dumps({
            "overall": {"level": "critical", "items_total": 1,
                        "items_critical": 1, "items_ok": 0, "items_degraded": 0,
                        "items_unknown": 0, "items_not_applicable": 0},
            "items": [{"id": "x", "name": "X", "status": "critical",
                       "detail": "down"}],
            "generated_at": "T1",
        }))
        with mock.patch.dict(os.environ,
                             {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "1"}):
            with mock.patch("alert_notifier.send_telegram",
                            return_value=True) as send:
                run_check(self.health, self.alert,
                          hardening_state_path=self.hardening)
        # Health is ok + no prior state → no health alert. Hardening first run silent.
        send.assert_not_called()
        st = json.loads(self.alert.read_text())
        self.assertEqual(st.get("last_hardening_level"), "critical")

    def test_hardening_transition_after_first_alerts(self):
        # First run: hardening ok (no alert)
        self.hardening.write_text(json.dumps({
            "overall": {"level": "ok", "items_total": 1, "items_ok": 1,
                        "items_critical": 0, "items_degraded": 0,
                        "items_unknown": 0, "items_not_applicable": 0},
            "items": [], "generated_at": "T1",
        }))
        with mock.patch.dict(os.environ,
                             {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "1"}):
            with mock.patch("alert_notifier.send_telegram", return_value=True):
                run_check(self.health, self.alert,
                          hardening_state_path=self.hardening)

        # Second run: hardening transitions to critical → alert with prefix
        self.hardening.write_text(json.dumps({
            "overall": {"level": "critical", "items_total": 1, "items_ok": 0,
                        "items_critical": 1, "items_degraded": 0,
                        "items_unknown": 0, "items_not_applicable": 0},
            "items": [{"id": "ufw-active", "name": "UFW", "status": "critical",
                       "detail": "down"}],
            "generated_at": "T2",
        }))
        with mock.patch.dict(os.environ,
                             {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "1"}):
            with mock.patch("alert_notifier.send_telegram",
                            return_value=True) as send:
                run_check(self.health, self.alert,
                          hardening_state_path=self.hardening)
        # Telegram called once for hardening alert
        self.assertEqual(send.call_count, 1)
        sent_msg = send.call_args[0][2]
        self.assertIn("[hardening]", sent_msg)
        st = json.loads(self.alert.read_text())
        self.assertEqual(st.get("last_hardening_level"), "critical")


if __name__ == "__main__":
    unittest.main()
