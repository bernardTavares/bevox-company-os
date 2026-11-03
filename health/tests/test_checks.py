"""Tests for check_systemd_active, check_http_url, check_file_freshness."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runner


class TestSystemdActive(unittest.TestCase):
    def test_active_returns_up(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="active\n", stderr="")
            result = runner.check_systemd_active({"unit": "foo.service"})
            self.assertEqual(result["status"], "up")
            self.assertEqual(result["detail"], "active")

    def test_inactive_returns_down(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=3, stdout="inactive\n", stderr="")
            result = runner.check_systemd_active({"unit": "foo.service"})
            self.assertEqual(result["status"], "down")
            self.assertEqual(result["detail"], "inactive")

    def test_failed_returns_down(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=3, stdout="failed\n", stderr="")
            result = runner.check_systemd_active({"unit": "foo.service"})
            self.assertEqual(result["status"], "down")
            self.assertEqual(result["detail"], "failed")

    def test_empty_stdout_returns_down(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stdout="", stderr="")
            result = runner.check_systemd_active({"unit": "foo.service"})
            self.assertEqual(result["status"], "down")
            self.assertEqual(result["detail"], "inactive")

    def test_timeout_returns_unknown(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["systemctl"], timeout=2)):
            result = runner.check_systemd_active({"unit": "foo.service"})
            self.assertEqual(result["status"], "unknown")
            self.assertIn("timeout", result["detail"].lower())

    def test_unexpected_exception_returns_unknown(self):
        with patch("subprocess.run", side_effect=OSError("no such file")):
            result = runner.check_systemd_active({"unit": "foo.service"})
            self.assertEqual(result["status"], "unknown")
            self.assertIn("OSError", result["detail"])

    def test_invocation_shape(self):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout="active\n", stderr="")
            runner.check_systemd_active({"unit": "myservice.timer"})
            args, kwargs = m.call_args
            self.assertEqual(args[0], ["systemctl", "--user", "is-active", "myservice.timer"])
            self.assertEqual(kwargs.get("timeout"), runner.SYSTEMCTL_TIMEOUT_SEC)
            self.assertTrue(kwargs.get("capture_output"))
            self.assertTrue(kwargs.get("text"))


class TestHttpUrl(unittest.TestCase):
    def _mock_response(self, status):
        resp = MagicMock()
        resp.status = status
        return resp

    def test_200_returns_up(self):
        with patch("urllib.request.urlopen") as m:
            m.return_value.__enter__ = lambda s: self._mock_response(200)
            m.return_value.__exit__ = MagicMock(return_value=False)
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200],
            })
            self.assertEqual(result["status"], "up")
            self.assertEqual(result["detail"], "200")

    def test_302_in_accept_returns_up(self):
        with patch("urllib.request.urlopen") as m:
            m.return_value.__enter__ = lambda s: self._mock_response(302)
            m.return_value.__exit__ = MagicMock(return_value=False)
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200, 302],
            })
            self.assertEqual(result["status"], "up")
            self.assertEqual(result["detail"], "302")

    def test_500_not_in_accept_returns_down(self):
        with patch("urllib.request.urlopen") as m:
            m.return_value.__enter__ = lambda s: self._mock_response(500)
            m.return_value.__exit__ = MagicMock(return_value=False)
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200],
            })
            self.assertEqual(result["status"], "down")
            self.assertEqual(result["detail"], "500")

    def test_http_error_code_in_accept_returns_up(self):
        from urllib.error import HTTPError
        with patch("urllib.request.urlopen", side_effect=HTTPError("url", 401, "Unauthorized", {}, None)):
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200, 401, 403],
            })
            self.assertEqual(result["status"], "up")
            self.assertEqual(result["detail"], "401")

    def test_http_error_code_not_in_accept_returns_down(self):
        from urllib.error import HTTPError
        with patch("urllib.request.urlopen", side_effect=HTTPError("url", 500, "Server Error", {}, None)):
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200],
            })
            self.assertEqual(result["status"], "down")
            self.assertEqual(result["detail"], "500")

    def test_url_error_returns_down(self):
        from urllib.error import URLError
        with patch("urllib.request.urlopen", side_effect=URLError("DNS failure")):
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200],
            })
            self.assertEqual(result["status"], "down")
            self.assertIn("URLError", result["detail"])

    def test_socket_timeout_returns_down(self):
        import socket
        with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
            result = runner.check_http_url({
                "url": "https://example.com",
                "timeout_sec": 5,
                "accept_status": [200],
            })
            self.assertEqual(result["status"], "down")

    def test_defaults_applied(self):
        """timeout_sec and accept_status defaults when missing."""
        with patch("urllib.request.urlopen") as m:
            m.return_value.__enter__ = lambda s: self._mock_response(200)
            m.return_value.__exit__ = MagicMock(return_value=False)
            result = runner.check_http_url({"url": "https://example.com"})
            self.assertEqual(result["status"], "up")


class TestFileFreshness(unittest.TestCase):
    def test_fresh_file_returns_up(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"hello")
        tmp.close()
        try:
            result = runner.check_file_freshness({
                "path": tmp.name,
                "max_age_sec": 3600,
            })
            self.assertEqual(result["status"], "up")
            self.assertIn("age", result["detail"])
        finally:
            Path(tmp.name).unlink()

    def test_old_file_returns_degraded(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"hello")
        tmp.close()
        try:
            # Set mtime to 1 hour ago
            old_time = time.time() - 3600
            os_mod = __import__("os")
            os_mod.utime(tmp.name, (old_time, old_time))
            result = runner.check_file_freshness({
                "path": tmp.name,
                "max_age_sec": 60,  # 1 min max, but file is 1 hour old
            })
            self.assertEqual(result["status"], "degraded")
            self.assertIn(">", result["detail"])
            self.assertIn("max", result["detail"])
        finally:
            Path(tmp.name).unlink()

    def test_missing_file_returns_down(self):
        result = runner.check_file_freshness({
            "path": "/tmp/does-not-exist-xyz-12345",
            "max_age_sec": 60,
        })
        self.assertEqual(result["status"], "down")
        self.assertIn("not found", result["detail"])

    def test_tilde_expansion(self):
        tmp = Path.home() / ".health-test-tmpfile"
        tmp.write_text("x")
        try:
            result = runner.check_file_freshness({
                "path": "~/.health-test-tmpfile",
                "max_age_sec": 3600,
            })
            self.assertEqual(result["status"], "up")
        finally:
            tmp.unlink()

    def test_age_included_in_detail(self):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"x")
        tmp.close()
        try:
            result = runner.check_file_freshness({
                "path": tmp.name,
                "max_age_sec": 3600,
            })
            self.assertRegex(result["detail"], r"age \d+s")
        finally:
            Path(tmp.name).unlink()


if __name__ == "__main__":
    unittest.main()
