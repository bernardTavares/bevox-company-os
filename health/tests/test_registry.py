"""Tests for load_registry + schema validation."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runner


VALID_YAML = """\
version: 1
services:
  foo:
    name: "Foo Service"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: foo.service
    since: 2026-04-14
"""


def _write_tmp_yaml(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


class TestLoadRegistryValid(unittest.TestCase):
    def test_valid_yaml_loads(self):
        p = _write_tmp_yaml(VALID_YAML)
        try:
            data = runner.load_registry(p)
            self.assertEqual(data["version"], 1)
            self.assertIn("foo", data["services"])
            self.assertEqual(data["services"]["foo"]["critical"], True)
        finally:
            p.unlink()

    def test_missing_file_raises(self):
        missing = Path("/tmp/does-not-exist-xyz-health.yml")
        with self.assertRaises(runner.RegistryError):
            runner.load_registry(missing)


class TestLoadRegistrySchema(unittest.TestCase):
    def test_version_must_be_1(self):
        p = _write_tmp_yaml("version: 2\nservices: {}\n")
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_empty_services_rejected(self):
        p = _write_tmp_yaml("version: 1\nservices: {}\n")
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_missing_required_field(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: foo.service
"""  # missing 'since'
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_invalid_check_type(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: made_up_check
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_systemd_active_empty_unit(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: ""
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_http_url_invalid_protocol(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: http_url
      url: ftp://example.com
      timeout_sec: 5
      accept_status: [200]
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_http_url_negative_timeout(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: http_url
      url: https://example.com
      timeout_sec: -1
      accept_status: [200]
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_file_freshness_missing_max_age(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: file_freshness
      path: /tmp/x
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_malformed_yaml_raises(self):
        p = _write_tmp_yaml("this is : : : not valid yaml ::::::")
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_empty_name_rejected(self):
        bad = """\
version: 1
services:
  foo:
    name: ""
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: foo.service
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_empty_owner_rejected(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: "   "
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: foo.service
    since: 2026-04-14
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()

    def test_invalid_since_format_rejected(self):
        bad = """\
version: 1
services:
  foo:
    name: "Foo"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: foo.service
    since: "14/04/2026"
"""
        p = _write_tmp_yaml(bad)
        try:
            with self.assertRaises(runner.RegistryError):
                runner.load_registry(p)
        finally:
            p.unlink()


if __name__ == "__main__":
    unittest.main()
