"""E8/F5 wave 1 — Hardening tracker runner tests.

Spec: bevox-knowledge/35_specs/2026-04-18-e8-f5-hardening-tracker-wave-1.md
"""
import os
import re
import sys
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runner


class TestComputeOverallLevel(unittest.TestCase):
    """Spec §5.3: overall.level computed in priority order:
        critical → unknown → degraded → ok.
    not_applicable items NEVER contribute.
    """

    def _items(self, *statuses):
        """Build minimal item dicts."""
        return [{"id": f"i{n}", "status": s} for n, s in enumerate(statuses)]

    def test_all_ok_returns_ok(self):
        self.assertEqual(runner._compute_overall_level(self._items("ok", "ok")), "ok")

    def test_empty_returns_ok(self):
        self.assertEqual(runner._compute_overall_level([]), "ok")

    def test_one_critical_returns_critical(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("ok", "critical", "ok")),
            "critical",
        )

    def test_critical_beats_unknown(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("unknown", "critical")),
            "critical",
        )

    def test_critical_beats_degraded(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("degraded", "critical", "degraded")),
            "critical",
        )

    def test_unknown_beats_degraded(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("degraded", "unknown")),
            "unknown",
        )

    def test_degraded_when_no_critical_or_unknown(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("ok", "degraded", "ok")),
            "degraded",
        )

    def test_not_applicable_does_not_count(self):
        # Mix of ok + not_applicable → still ok
        self.assertEqual(
            runner._compute_overall_level(self._items("ok", "not_applicable", "ok")),
            "ok",
        )

    def test_only_not_applicable_returns_ok(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("not_applicable", "not_applicable")),
            "ok",
        )

    def test_not_applicable_does_not_mask_critical(self):
        self.assertEqual(
            runner._compute_overall_level(self._items("not_applicable", "critical")),
            "critical",
        )


class TestParseRegexFlags(unittest.TestCase):
    """Helper: convert ['multiline', 'ignorecase', 'dotall'] → int flags."""

    def test_empty_list_returns_zero(self):
        self.assertEqual(runner._parse_regex_flags([]), 0)

    def test_multiline(self):
        self.assertEqual(runner._parse_regex_flags(["multiline"]), re.MULTILINE)

    def test_ignorecase(self):
        self.assertEqual(runner._parse_regex_flags(["ignorecase"]), re.IGNORECASE)

    def test_dotall(self):
        self.assertEqual(runner._parse_regex_flags(["dotall"]), re.DOTALL)

    def test_combined(self):
        flags = runner._parse_regex_flags(["multiline", "ignorecase"])
        self.assertEqual(flags, re.MULTILINE | re.IGNORECASE)

    def test_unknown_flag_raises(self):
        with self.assertRaises(ValueError) as ctx:
            runner._parse_regex_flags(["bogus"])
        self.assertIn("bogus", str(ctx.exception))

    def test_case_insensitive_match(self):
        # Implementation may accept either case; spec uses lowercase
        flags = runner._parse_regex_flags(["MULTILINE"])
        self.assertEqual(flags, re.MULTILINE)


class TestSeverityToFailedStatus(unittest.TestCase):
    """Helper: map severity → status when check fails.

    Spec §5.3: severity=critical → status critical; severity warn|info → degraded.
    """

    def test_critical_severity_becomes_critical(self):
        self.assertEqual(runner._severity_to_failed_status("critical"), "critical")

    def test_warn_severity_becomes_degraded(self):
        self.assertEqual(runner._severity_to_failed_status("warn"), "degraded")

    def test_info_severity_becomes_degraded(self):
        self.assertEqual(runner._severity_to_failed_status("info"), "degraded")


class TestComputeOverallSummary(unittest.TestCase):
    """Helper: build the overall.* counters dict from item list."""

    def test_counts_all_buckets(self):
        items = [
            {"status": "ok"}, {"status": "ok"}, {"status": "ok"},
            {"status": "degraded"},
            {"status": "critical"}, {"status": "critical"},
            {"status": "unknown"},
            {"status": "not_applicable"},
        ]
        result = runner._compute_overall_summary(items)
        self.assertEqual(result["items_total"], 8)
        self.assertEqual(result["items_ok"], 3)
        self.assertEqual(result["items_degraded"], 1)
        self.assertEqual(result["items_critical"], 2)
        self.assertEqual(result["items_unknown"], 1)
        self.assertEqual(result["items_not_applicable"], 1)


class TestCheckSystemdActive(unittest.TestCase):
    """Spec §5.2: systemd_active.

    Returns dict {status, detail}. Mock subprocess.run.
    """

    def _params(self, **overrides):
        d = {"unit": "ufw.service", "scope": "system",
             "not_applicable_if_unit_missing": False}
        d.update(overrides)
        return d

    def test_active_returns_ok(self):
        m = MagicMock(returncode=0, stdout="active\n", stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_systemd_active(self._params())
        self.assertEqual(result["status"], "ok")
        self.assertIn("active", result["detail"])

    def test_inactive_returns_failed(self):
        m = MagicMock(returncode=3, stdout="inactive\n", stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_systemd_active(self._params())
        self.assertEqual(result["status"], "failed")
        self.assertIn("inactive", result["detail"])

    def test_unit_missing_with_opt_in_returns_not_applicable(self):
        m = MagicMock(returncode=4, stdout="",
                      stderr="Unit nonexistent.service could not be found.\n")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_systemd_active(self._params(
                unit="nonexistent.service", not_applicable_if_unit_missing=True))
        self.assertEqual(result["status"], "not_applicable")

    def test_unit_missing_without_opt_in_returns_failed(self):
        m = MagicMock(returncode=4, stdout="",
                      stderr="Unit nonexistent.service could not be found.\n")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_systemd_active(self._params(
                unit="nonexistent.service"))
        self.assertEqual(result["status"], "failed")

    def test_user_scope_uses_user_flag(self):
        m = MagicMock(returncode=0, stdout="active\n", stderr="")
        with patch("runner.subprocess.run", return_value=m) as p:
            runner._check_systemd_active(self._params(scope="user"))
        cmd = p.call_args[0][0]
        self.assertIn("--user", cmd)

    def test_system_scope_no_user_flag(self):
        m = MagicMock(returncode=0, stdout="active\n", stderr="")
        with patch("runner.subprocess.run", return_value=m) as p:
            runner._check_systemd_active(self._params(scope="system"))
        cmd = p.call_args[0][0]
        self.assertNotIn("--user", cmd)

    def test_systemctl_not_installed_returns_unknown(self):
        with patch("runner.subprocess.run", side_effect=FileNotFoundError("systemctl")):
            result = runner._check_systemd_active(self._params())
        self.assertEqual(result["status"], "unknown")


class TestCheckCommandOutputMatch(unittest.TestCase):

    def _params(self, **overrides):
        d = {"cmd": ["echo", "hello"], "expect_regex": "hello",
             "regex_flags": [], "timeout_sec": 5,
             "not_applicable_on_exit": [], "not_applicable_if_cmd_missing": False}
        d.update(overrides)
        return d

    def test_match_returns_ok(self):
        m = MagicMock(returncode=0, stdout="hello\n", stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_command_output_match(self._params())
        self.assertEqual(result["status"], "ok")

    def test_no_match_returns_failed(self):
        m = MagicMock(returncode=0, stdout="goodbye\n", stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_command_output_match(self._params())
        self.assertEqual(result["status"], "failed")

    def test_nonzero_exit_returns_failed(self):
        m = MagicMock(returncode=1, stdout="hello\n", stderr="oops")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_command_output_match(self._params())
        self.assertEqual(result["status"], "failed")

    def test_not_applicable_on_exit_match(self):
        m = MagicMock(returncode=4, stdout="", stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_command_output_match(self._params(
                not_applicable_on_exit=[4]))
        self.assertEqual(result["status"], "not_applicable")

    def test_cmd_missing_with_opt_in_returns_not_applicable(self):
        with patch("runner.subprocess.run", side_effect=FileNotFoundError("nocmd")):
            result = runner._check_command_output_match(self._params(
                not_applicable_if_cmd_missing=True))
        self.assertEqual(result["status"], "not_applicable")

    def test_cmd_missing_without_opt_in_returns_unknown(self):
        with patch("runner.subprocess.run", side_effect=FileNotFoundError("nocmd")):
            result = runner._check_command_output_match(self._params())
        self.assertEqual(result["status"], "unknown")

    def test_timeout_returns_unknown(self):
        with patch("runner.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5)):
            result = runner._check_command_output_match(self._params())
        self.assertEqual(result["status"], "unknown")
        self.assertIn("timeout", result["detail"].lower())


class TestCheckFileModeEq(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _params(self, path=None, mode="0600", **overrides):
        d = {"path": str(path) if path else "/nonexistent", "mode": mode,
             "not_applicable_if_missing": False}
        d.update(overrides)
        return d

    def test_mode_matches_returns_ok(self):
        f = self.tmpdir / "test.cfg"
        f.write_text("x")
        os.chmod(f, 0o600)
        result = runner._check_file_mode_eq(self._params(path=f, mode="0600"))
        self.assertEqual(result["status"], "ok")

    def test_mode_differs_returns_failed(self):
        f = self.tmpdir / "test.cfg"
        f.write_text("x")
        os.chmod(f, 0o644)
        result = runner._check_file_mode_eq(self._params(path=f, mode="0600"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("0644", result["detail"])

    def test_missing_without_opt_in_returns_unknown(self):
        result = runner._check_file_mode_eq(self._params(
            path=self.tmpdir / "ghost"))
        self.assertEqual(result["status"], "unknown")

    def test_missing_with_opt_in_returns_not_applicable(self):
        result = runner._check_file_mode_eq(self._params(
            path=self.tmpdir / "ghost", not_applicable_if_missing=True))
        self.assertEqual(result["status"], "not_applicable")


class TestCheckFileContentMatch(unittest.TestCase):

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _params(self, paths, expect_regex, **overrides):
        d = {"paths": paths, "expect_regex": expect_regex,
             "regex_flags": [], "match_mode": "any",
             "forbid_regex": None, "not_applicable_if_no_files": False,
             "max_total_bytes": 1048576}
        d.update(overrides)
        return d

    def test_single_file_match_returns_ok(self):
        f = self.tmpdir / "ssh.conf"
        f.write_text("PasswordAuthentication no\n")
        result = runner._check_file_content_match(self._params(
            paths=[str(f)],
            expect_regex=r"^PasswordAuthentication\s+no\s*$",
            regex_flags=["multiline"]))
        self.assertEqual(result["status"], "ok")

    def test_no_match_returns_failed(self):
        f = self.tmpdir / "ssh.conf"
        f.write_text("PasswordAuthentication yes\n")
        result = runner._check_file_content_match(self._params(
            paths=[str(f)],
            expect_regex=r"^PasswordAuthentication\s+no\s*$",
            regex_flags=["multiline"]))
        self.assertEqual(result["status"], "failed")

    def test_glob_paths_expand(self):
        (self.tmpdir / "a.conf").write_text("foo\n")
        (self.tmpdir / "b.conf").write_text("PasswordAuthentication no\n")
        result = runner._check_file_content_match(self._params(
            paths=[str(self.tmpdir / "*.conf")],
            expect_regex=r"^PasswordAuthentication\s+no\s*$",
            regex_flags=["multiline"]))
        self.assertEqual(result["status"], "ok")

    def test_match_mode_any_first_file_match(self):
        (self.tmpdir / "a.conf").write_text("PasswordAuthentication no\n")
        (self.tmpdir / "b.conf").write_text("PasswordAuthentication yes\n")
        result = runner._check_file_content_match(self._params(
            paths=[str(self.tmpdir / "a.conf"), str(self.tmpdir / "b.conf")],
            expect_regex=r"^PasswordAuthentication\s+no\s*$",
            regex_flags=["multiline"],
            match_mode="any"))
        self.assertEqual(result["status"], "ok")

    def test_match_mode_all_requires_all(self):
        (self.tmpdir / "a.conf").write_text("PasswordAuthentication no\n")
        (self.tmpdir / "b.conf").write_text("OtherSetting yes\n")
        result = runner._check_file_content_match(self._params(
            paths=[str(self.tmpdir / "a.conf"), str(self.tmpdir / "b.conf")],
            expect_regex=r"^PasswordAuthentication\s+no\s*$",
            regex_flags=["multiline"],
            match_mode="all"))
        self.assertEqual(result["status"], "failed")

    def test_forbid_regex_overrides_ok(self):
        (self.tmpdir / "a.conf").write_text("PasswordAuthentication no\n")
        (self.tmpdir / "b.conf").write_text("PasswordAuthentication yes\n")
        result = runner._check_file_content_match(self._params(
            paths=[str(self.tmpdir / "*.conf")],
            expect_regex=r"^PasswordAuthentication\s+no\s*$",
            regex_flags=["multiline"],
            forbid_regex=r"^PasswordAuthentication\s+yes\s*$"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("forbid", result["detail"].lower())

    def test_no_files_without_opt_in_returns_unknown(self):
        result = runner._check_file_content_match(self._params(
            paths=[str(self.tmpdir / "ghost*.conf")],
            expect_regex="x"))
        self.assertEqual(result["status"], "unknown")

    def test_no_files_with_opt_in_returns_not_applicable(self):
        result = runner._check_file_content_match(self._params(
            paths=[str(self.tmpdir / "ghost*.conf")],
            expect_regex="x",
            not_applicable_if_no_files=True))
        self.assertEqual(result["status"], "not_applicable")

    def test_byte_budget_exceeded_returns_unknown(self):
        f = self.tmpdir / "big.conf"
        f.write_text("x" * 200)
        result = runner._check_file_content_match(self._params(
            paths=[str(f)], expect_regex="x", max_total_bytes=100))
        self.assertEqual(result["status"], "unknown")
        self.assertIn("byte", result["detail"].lower())


class TestCheckAptSecurityUpdatesMax(unittest.TestCase):

    def _params(self, threshold=5, timeout_sec=30):
        return {"threshold": threshold, "timeout_sec": timeout_sec}

    def test_below_threshold_returns_ok(self):
        # apt-get -s upgrade output with 2 security updates
        out = "Inst libc6 [2.36-9] (2.36-10 Debian-Security:1)\n" \
              "Inst openssl [3.0.11-1] (3.0.12-1 Debian-Security:1)\n"
        m = MagicMock(returncode=0, stdout=out, stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_apt_security_updates_max(self._params(threshold=5))
        self.assertEqual(result["status"], "ok")
        self.assertIn("2", result["detail"])

    def test_at_threshold_returns_ok(self):
        out = "\n".join(f"Inst pkg{i} [1.0] (1.1 Debian-Security:x)" for i in range(5))
        m = MagicMock(returncode=0, stdout=out, stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_apt_security_updates_max(self._params(threshold=5))
        self.assertEqual(result["status"], "ok")

    def test_above_threshold_returns_failed(self):
        out = "\n".join(f"Inst pkg{i} [1.0] (1.1 Debian-Security:x)" for i in range(10))
        m = MagicMock(returncode=0, stdout=out, stderr="")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_apt_security_updates_max(self._params(threshold=5))
        self.assertEqual(result["status"], "failed")

    def test_apt_not_installed_returns_not_applicable(self):
        with patch("runner.subprocess.run", side_effect=FileNotFoundError("apt-get")):
            result = runner._check_apt_security_updates_max(self._params())
        self.assertEqual(result["status"], "not_applicable")

    def test_unexpected_error_returns_unknown(self):
        m = MagicMock(returncode=99, stdout="", stderr="something broke")
        with patch("runner.subprocess.run", return_value=m):
            result = runner._check_apt_security_updates_max(self._params())
        self.assertEqual(result["status"], "unknown")


class TestEvaluateItem(unittest.TestCase):
    """Orchestrator: evaluate one item from registry → state-shape dict."""

    def test_ok_handler_result_propagates_status(self):
        item = {
            "id": "ufw-active", "name": "UFW", "category": "firewall",
            "severity": "critical",
            "check": {"type": "systemd_active", "unit": "ufw.service",
                      "scope": "system"},
        }
        with patch("runner._check_systemd_active",
                   return_value={"status": "ok", "detail": "active"}):
            result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["id"], "ufw-active")
        self.assertEqual(result["check_type"], "systemd_active")
        self.assertIn("checked_at", result)
        self.assertIn("duration_ms", result)

    def test_failed_with_critical_severity_becomes_critical(self):
        item = {
            "id": "x", "name": "X", "category": "ssh", "severity": "critical",
            "check": {"type": "systemd_active", "unit": "x.service"},
        }
        with patch("runner._check_systemd_active",
                   return_value={"status": "failed", "detail": "down"}):
            result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "critical")

    def test_failed_with_warn_severity_becomes_degraded(self):
        item = {
            "id": "x", "name": "X", "category": "updates", "severity": "warn",
            "check": {"type": "systemd_active", "unit": "x.service"},
        }
        with patch("runner._check_systemd_active",
                   return_value={"status": "failed", "detail": "down"}):
            result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "degraded")

    def test_not_applicable_propagates(self):
        item = {
            "id": "x", "name": "X", "category": "ssh", "severity": "critical",
            "check": {"type": "systemd_active", "unit": "x.service"},
        }
        with patch("runner._check_systemd_active",
                   return_value={"status": "not_applicable", "detail": "n/a"}):
            result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "not_applicable")

    def test_unknown_propagates(self):
        item = {
            "id": "x", "name": "X", "category": "ssh", "severity": "critical",
            "check": {"type": "systemd_active", "unit": "x.service"},
        }
        with patch("runner._check_systemd_active",
                   return_value={"status": "unknown", "detail": "?"}):
            result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "unknown")

    def test_handler_exception_returns_unknown(self):
        item = {
            "id": "x", "name": "X", "category": "ssh", "severity": "critical",
            "check": {"type": "systemd_active", "unit": "x.service"},
        }
        with patch("runner._check_systemd_active",
                   side_effect=RuntimeError("boom")):
            result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("boom", result["detail"])

    def test_unknown_check_type_returns_unknown(self):
        item = {
            "id": "x", "name": "X", "category": "x", "severity": "warn",
            "check": {"type": "bogus_type"},
        }
        result = runner._evaluate_item(item)
        self.assertEqual(result["status"], "unknown")


class TestLoadRegistry(unittest.TestCase):
    """Loads + validates hardening-registry.yml shape."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.reg = self.tmpdir / "registry.yml"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, content):
        self.reg.write_text(content)
        return self.reg

    def test_loads_valid_registry(self):
        path = self._write("""\
version: 1
items:
  ufw-active:
    name: "UFW"
    category: firewall
    severity: critical
    check:
      type: systemd_active
      unit: ufw.service
      scope: system
    since: 2026-04-19
    description: x
""")
        result = runner._load_registry(path)
        self.assertEqual(result["version"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["id"], "ufw-active")

    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            runner._load_registry(self.tmpdir / "missing.yml")

    def test_invalid_check_type_raises(self):
        path = self._write("""\
version: 1
items:
  bad-item:
    name: "Bad"
    category: x
    severity: warn
    check:
      type: bogus
    since: 2026-04-19
    description: x
""")
        with self.assertRaises(ValueError) as ctx:
            runner._load_registry(path)
        self.assertIn("bogus", str(ctx.exception))

    def test_invalid_severity_raises(self):
        path = self._write("""\
version: 1
items:
  bad-item:
    name: "Bad"
    category: x
    severity: bogus
    check:
      type: systemd_active
      unit: x.service
    since: 2026-04-19
    description: x
""")
        with self.assertRaises(ValueError) as ctx:
            runner._load_registry(path)
        self.assertIn("bogus", str(ctx.exception))


class TestRunnerE2E(unittest.TestCase):
    """End-to-end: registry → run all items → write state.json atomic."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.reg = self.tmpdir / "registry.yml"
        self.state = self.tmpdir / "state.json"
        self.reg.write_text("""\
version: 1
items:
  always-ok:
    name: "Always OK"
    category: x
    severity: warn
    check:
      type: file_mode_eq
      path: /tmp
      mode: "1777"
    since: 2026-04-19
    description: x
""")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_writes_state_atomic(self):
        runner.run_scan(registry_path=self.reg, state_path=self.state)
        self.assertTrue(self.state.exists())
        import json as _json
        state = _json.loads(self.state.read_text())
        self.assertEqual(state["schema_version"], runner.SCHEMA_VERSION)
        self.assertEqual(state["overall"]["level"], "ok")
        self.assertEqual(state["overall"]["items_total"], 1)
        self.assertEqual(state["overall"]["items_ok"], 1)
        self.assertEqual(len(state["items"]), 1)
        self.assertEqual(state["items"][0]["id"], "always-ok")

    def test_run_atomic_no_partial_on_io_error(self):
        # Pre-existing state should survive write failure
        self.state.write_text('{"prior": "intact"}')
        # Force tmp rename to fail by making state path a directory
        bad_state = self.tmpdir / "asdir"
        bad_state.mkdir()
        with self.assertRaises(Exception):
            runner.run_scan(registry_path=self.reg, state_path=bad_state)
        # Original file untouched
        import json as _json
        self.assertEqual(_json.loads(self.state.read_text()), {"prior": "intact"})

    def test_run_with_critical_failure_overall_critical(self):
        self.reg.write_text("""\
version: 1
items:
  failing:
    name: "Failing"
    category: x
    severity: critical
    check:
      type: file_mode_eq
      path: /tmp
      mode: "0000"
    since: 2026-04-19
    description: x
""")
        runner.run_scan(registry_path=self.reg, state_path=self.state)
        import json as _json
        state = _json.loads(self.state.read_text())
        self.assertEqual(state["overall"]["level"], "critical")


if __name__ == "__main__":
    unittest.main()
