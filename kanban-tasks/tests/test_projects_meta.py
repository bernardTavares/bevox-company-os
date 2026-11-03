"""Tests for projects-meta.json read/write atomic helpers.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.5
W1 extension: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import projects_meta
from lib.projects_meta import (
    CAPABILITY_NAMES,
    CAPABILITY_SCHEMA_VERSION,
    CAPABILITY_STATES,
    SCHEMA_VERSION,
    MetaError,
    delete_project,
    empty_capability_set,
    get_adr_prefix,
    get_capability,
    insert_project,
    is_legacy_entry,
    is_legacy_meta,
    read_meta,
    set_capability_state,
    update_project,
    write_meta,
)


class TestReadMeta(unittest.TestCase):
    def test_creates_empty_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            data = read_meta(meta_path)
            self.assertEqual(data, {"version": 1, "projects": {}})
            # Doesn't write — only returns default
            self.assertFalse(meta_path.exists())

    def test_returns_existing_data(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {"foo": {"name": "Foo"}}}')
            data = read_meta(meta_path)
            self.assertEqual(data["projects"]["foo"]["name"], "Foo")


class TestWriteMeta(unittest.TestCase):
    def test_atomic_via_tmp_rename(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            write_meta(meta_path, {"version": 1, "projects": {"x": {"name": "X"}}})
            self.assertTrue(meta_path.exists())
            data = json.loads(meta_path.read_text())
            self.assertEqual(data["projects"]["x"]["name"], "X")
            # tmp file should be gone
            self.assertFalse((Path(td) / "meta.json.tmp").exists())


class TestInsertProject(unittest.TestCase):
    def test_creates_entry(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            insert_project(meta_path, "customer-portal", {
                "name": "Customer Portal",
                "description": "App",
                "github_url": None,
                "bot_id": None,
                "created_at": "2026-04-26T00:00:00Z",
                "source": "user_created",
            })
            data = json.loads(meta_path.read_text())
            self.assertEqual(data["projects"]["customer-portal"]["name"], "Customer Portal")

    def test_fails_if_exists(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            insert_project(meta_path, "x", {"name": "X"})
            with self.assertRaises(MetaError) as ctx:
                insert_project(meta_path, "x", {"name": "X again"})
            self.assertIn("already exists", str(ctx.exception))


class TestUpdateProject(unittest.TestCase):
    def test_merges_partial(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            insert_project(meta_path, "x", {
                "name": "X", "description": "old", "bot_id": None,
            })
            update_project(meta_path, "x", {"bot_id": "8042:abc", "description": "new"})
            data = json.loads(meta_path.read_text())
            self.assertEqual(data["projects"]["x"]["bot_id"], "8042:abc")
            self.assertEqual(data["projects"]["x"]["description"], "new")
            self.assertEqual(data["projects"]["x"]["name"], "X")  # unchanged

    def test_fails_if_missing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            with self.assertRaises(MetaError) as ctx:
                update_project(meta_path, "missing", {"bot_id": "x"})
            self.assertIn("not found", str(ctx.exception))


class TestDeleteProject(unittest.TestCase):
    def test_removes_existing_entry(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            insert_project(meta_path, "x", {"name": "X"})
            delete_project(meta_path, "x")
            data = json.loads(meta_path.read_text())
            self.assertNotIn("x", data["projects"])

    def test_fails_if_missing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text('{"version": 1, "projects": {}}')
            with self.assertRaises(MetaError) as ctx:
                delete_project(meta_path, "ghost")
            self.assertIn("not found", str(ctx.exception))


# ============ W1: Capability state machine ============


class TestLegacyDetection(unittest.TestCase):
    def test_is_legacy_entry_missing_marker(self):
        self.assertTrue(is_legacy_entry({"name": "X"}))

    def test_is_legacy_entry_wrong_version(self):
        self.assertTrue(is_legacy_entry({"capabilities_schema_version": 0}))

    def test_is_legacy_entry_current_version(self):
        self.assertFalse(is_legacy_entry(
            {"capabilities_schema_version": CAPABILITY_SCHEMA_VERSION}
        ))

    def test_is_legacy_meta_mixed(self):
        data = {
            "version": 1,
            "projects": {
                "a": {"capabilities_schema_version": CAPABILITY_SCHEMA_VERSION},
                "b": {"name": "B"},  # legacy
            },
        }
        self.assertTrue(is_legacy_meta(data))

    def test_is_legacy_meta_all_migrated(self):
        data = {
            "version": 1,
            "projects": {
                "a": {"capabilities_schema_version": CAPABILITY_SCHEMA_VERSION},
            },
        }
        self.assertFalse(is_legacy_meta(data))

    def test_is_legacy_meta_empty(self):
        self.assertFalse(is_legacy_meta({"version": 1, "projects": {}}))


class TestEmptyCapabilitySet(unittest.TestCase):
    def test_returns_all_8_capabilities_absent(self):
        caps = empty_capability_set()
        self.assertEqual(set(caps.keys()), set(CAPABILITY_NAMES))
        for name in CAPABILITY_NAMES:
            self.assertEqual(caps[name], {"state": "absent"})


class TestGetCapability(unittest.TestCase):
    def _seed_meta(self, td: str) -> Path:
        meta_path = Path(td) / "meta.json"
        meta_path.write_text(json.dumps({
            "version": 1,
            "projects": {
                "x": {
                    "name": "X",
                    "capabilities_schema_version": CAPABILITY_SCHEMA_VERSION,
                    "capabilities": {
                        "code_repo": {"state": "provisioned", "path": "/code/x"},
                    },
                },
            },
        }))
        return meta_path

    def test_returns_existing_capability(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed_meta(td)
            cap = get_capability(meta_path, "x", "code_repo")
            self.assertEqual(cap["state"], "provisioned")
            self.assertEqual(cap["path"], "/code/x")

    def test_returns_absent_if_capability_missing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed_meta(td)
            cap = get_capability(meta_path, "x", "bot")
            self.assertEqual(cap, {"state": "absent"})

    def test_returns_absent_if_slug_missing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed_meta(td)
            cap = get_capability(meta_path, "ghost", "code_repo")
            self.assertEqual(cap, {"state": "absent"})

    def test_accepts_meta_dict(self):
        meta = {
            "version": 1,
            "projects": {
                "y": {
                    "capabilities_schema_version": CAPABILITY_SCHEMA_VERSION,
                    "capabilities": {"workspace": {"state": "partial"}},
                },
            },
        }
        cap = get_capability(meta, "y", "workspace")
        self.assertEqual(cap["state"], "partial")

    def test_unknown_capability_raises(self):
        with self.assertRaises(MetaError) as ctx:
            get_capability({}, "x", "garbage")
        self.assertIn("unknown capability", str(ctx.exception))


class TestSetCapabilityState(unittest.TestCase):
    def _seed(self, td: str, **kwargs) -> Path:
        meta_path = Path(td) / "meta.json"
        meta_path.write_text(json.dumps({
            "version": 1,
            "projects": {
                "x": {"name": "X", **kwargs},
            },
        }))
        return meta_path

    def test_creates_capability_in_legacy_entry(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed(td)
            set_capability_state(
                meta_path, "x", "code_repo",
                "provisioned", path="/code/x", github="org/x",
            )
            data = json.loads(meta_path.read_text())
            entry = data["projects"]["x"]
            self.assertEqual(
                entry["capabilities_schema_version"], CAPABILITY_SCHEMA_VERSION
            )
            self.assertEqual(
                entry["capabilities"]["code_repo"],
                {"state": "provisioned", "path": "/code/x", "github": "org/x"},
            )

    def test_merges_fields_preserving_existing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed(
                td,
                capabilities_schema_version=CAPABILITY_SCHEMA_VERSION,
                capabilities={
                    "code_repo": {"state": "partial", "path": "/code/x"},
                },
            )
            set_capability_state(
                meta_path, "x", "code_repo", "provisioned", github="org/x"
            )
            data = json.loads(meta_path.read_text())
            cap = data["projects"]["x"]["capabilities"]["code_repo"]
            self.assertEqual(cap["state"], "provisioned")
            self.assertEqual(cap["path"], "/code/x")  # preserved
            self.assertEqual(cap["github"], "org/x")

    def test_invalid_state_raises(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed(td)
            with self.assertRaises(MetaError) as ctx:
                set_capability_state(meta_path, "x", "code_repo", "garbage")
            self.assertIn("invalid capability state", str(ctx.exception))

    def test_invalid_capability_raises(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed(td)
            with self.assertRaises(MetaError) as ctx:
                set_capability_state(meta_path, "x", "bogus", "provisioned")
            self.assertIn("unknown capability", str(ctx.exception))

    def test_missing_slug_raises(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed(td)
            with self.assertRaises(MetaError) as ctx:
                set_capability_state(meta_path, "ghost", "code_repo", "provisioned")
            self.assertIn("not found", str(ctx.exception))

    def test_all_4_states_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = self._seed(td)
            for state in CAPABILITY_STATES:
                set_capability_state(meta_path, "x", "workspace", state)
                data = json.loads(meta_path.read_text())
                self.assertEqual(
                    data["projects"]["x"]["capabilities"]["workspace"]["state"],
                    state,
                )


class TestLegacyWarning(unittest.TestCase):
    def setUp(self):
        # Reset the in-process warned set so tests don't leak state.
        projects_meta._LEGACY_WARNED.clear()

    def test_emits_warning_once(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text(json.dumps({
                "version": 1,
                "projects": {"x": {"name": "X"}},  # legacy
            }))
            buf = io.StringIO()
            with patch("sys.stderr", buf):
                read_meta(meta_path)
                read_meta(meta_path)  # 2nd call — should NOT re-emit
            output = buf.getvalue()
            self.assertEqual(output.count("schema legacy"), 1)
            self.assertIn("migrate-meta", output)

    def test_no_warning_for_migrated_meta(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "meta.json"
            meta_path.write_text(json.dumps({
                "version": 1,
                "projects": {
                    "x": {
                        "capabilities_schema_version": CAPABILITY_SCHEMA_VERSION,
                        "capabilities": empty_capability_set(),
                    },
                },
            }))
            buf = io.StringIO()
            with patch("sys.stderr", buf):
                read_meta(meta_path)
            self.assertEqual(buf.getvalue(), "")


class TestKnowledgeWatcher(unittest.TestCase):
    """Tests for knowledge_watcher config field in projects-meta entries."""

    def test_default_entry_includes_knowledge_watcher_config(self):
        """New project entries default to knowledge_watcher opt_in=true.

        Tested via _ensure_meta_entry which is the code path adopt uses.
        """
        from lib.cli.cmd_project_adopt import _ensure_meta_entry

        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "projects-meta.json"
            # Initialize empty meta
            write_meta(meta_path, {"version": SCHEMA_VERSION, "projects": {}})
            entry = _ensure_meta_entry(
                meta_path=meta_path,
                slug="test-slug",
                description="test desc",
                domain="test-domain",
            )
            self.assertIn("knowledge_watcher", entry)
            self.assertIs(entry["knowledge_watcher"]["opt_in"], True)
            self.assertIsNone(entry["knowledge_watcher"]["last_run_at"])

    def test_is_knowledge_watcher_opted_in_default_when_field_absent(self):
        """Backward-compat: entries pre-W0 sem field are treated as opt-in."""
        legacy_entry = {"name": "old-proj", "capabilities": {}}
        self.assertTrue(projects_meta.is_knowledge_watcher_opted_in(legacy_entry))

    def test_is_knowledge_watcher_opted_in_respects_opt_out(self):
        """Opt-out via knowledge_watcher.opt_in=false."""
        entry = {"name": "x", "knowledge_watcher": {"opt_in": False}}
        self.assertFalse(projects_meta.is_knowledge_watcher_opted_in(entry))


class TestGetAdrPrefix(unittest.TestCase):
    """Tests for get_adr_prefix helper — read adr_prefix override from projects-meta."""

    def test_get_adr_prefix_returns_config_value(self):
        """Happy path: dict schema with adr_prefix set."""
        meta = {
            "projects": {
                "bevox-meta-api": {
                    "capabilities": {
                        "knowledge_watcher": {"opt_in": True, "adr_prefix": "MA"}
                    }
                }
            }
        }
        result = get_adr_prefix("bevox-meta-api", meta)
        self.assertEqual(result, "MA")

    def test_get_adr_prefix_returns_none_when_absent(self):
        """Missing adr_prefix field returns None (auto-detect mode)."""
        meta = {"projects": {"bevox-direct": {}}}
        result = get_adr_prefix("bevox-direct", meta)
        self.assertIsNone(result)

    def test_get_adr_prefix_returns_none_when_project_missing(self):
        """Missing project slug returns None."""
        meta = {"projects": {}}
        result = get_adr_prefix("nonexistent", meta)
        self.assertIsNone(result)

    def test_get_adr_prefix_handles_list_schema(self):
        """Support legacy list-of-projects schema."""
        meta = {
            "projects": [
                {
                    "id": "bevox-meta-api",
                    "capabilities": {"knowledge_watcher": {"adr_prefix": "MA"}},
                }
            ]
        }
        result = get_adr_prefix("bevox-meta-api", meta)
        self.assertEqual(result, "MA")


if __name__ == "__main__":
    unittest.main()
