"""Tests for projects-meta capability schema migration.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md §Migration
"""
import json
import tempfile
import unittest
from pathlib import Path

from lib.capability_detect import DetectPaths
from lib.migration_capabilities import migrate_meta
from lib.projects_meta import (
    CAPABILITY_SCHEMA_VERSION,
    is_legacy_entry,
    is_legacy_meta,
)


def _make_paths(td: str) -> DetectPaths:
    base = Path(td)
    return DetectPaths(
        kb_dir=base / "kb",
        openclaw_dir=base / "openclaw",
        code_dir=base / "code",
        org="bernardTavares",
    )


def _seed_legacy_meta(td: str) -> Path:
    """Write a legacy projects-meta.json with 2 entries (no capabilities)."""
    meta_path = Path(td) / "openclaw" / "projects-meta.json"
    meta_path.parent.mkdir(parents=True)
    meta_path.write_text(json.dumps({
        "version": 1,
        "projects": {
            "alpha": {
                "name": "Alpha",
                "description": "first project",
                "github_url": "https://github.com/bernardTavares/alpha",
                "bot_id": "alpha-bot",
                "bot_port": 8042,
                "telegram": {"topics": {
                    "clarifications": 17, "dispatcher": 18, "blocks": 19,
                }},
                "created_at": "2026-04-01T00:00:00Z",
                "source": "user_created",
            },
            "beta": {
                "name": "Beta",
                "description": "",
                "github_url": None,
                "bot_id": None,
                "created_at": "2026-04-15T00:00:00Z",
                "source": "user_created",
            },
        },
    }))
    return meta_path


class TestMigrateMetaDryRun(unittest.TestCase):
    def test_returns_diff_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            pre_content = meta_path.read_text()
            paths = _make_paths(td)
            result = migrate_meta(
                meta_path, dry_run=True, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            self.assertTrue(result["dry_run"])
            self.assertEqual(set(result["migrated"]), {"alpha", "beta"})
            self.assertEqual(result["skipped"], [])
            self.assertIsNone(result["backup_path"])
            self.assertEqual(meta_path.read_text(), pre_content)
            # Diff includes both projects
            self.assertIn("alpha", result["diff"])
            self.assertIn("beta", result["diff"])


class TestMigrateMetaWriteAndBackup(unittest.TestCase):
    def test_writes_capabilities_and_creates_backup(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            paths = _make_paths(td)
            result = migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            self.assertEqual(set(result["migrated"]), {"alpha", "beta"})
            self.assertIsNotNone(result["backup_path"])
            self.assertTrue(Path(result["backup_path"]).exists())

            # Reload and verify capabilities populated
            data = json.loads(meta_path.read_text())
            for slug in ("alpha", "beta"):
                entry = data["projects"][slug]
                self.assertEqual(
                    entry["capabilities_schema_version"],
                    CAPABILITY_SCHEMA_VERSION,
                )
                self.assertIn("capabilities", entry)
                self.assertEqual(set(entry["capabilities"].keys()), {
                    "code_repo", "knowledge_slot", "kanban_sprints",
                    "workspace", "persona", "bot",
                    "telegram_topics", "mission_control",
                })

            # Top-level legacy fields preserved (compat readers)
            self.assertEqual(
                data["projects"]["alpha"]["bot_id"], "alpha-bot",
            )
            self.assertEqual(
                data["projects"]["alpha"]["github_url"],
                "https://github.com/bernardTavares/alpha",
            )

    def test_backup_not_overwritten_on_rerun(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            paths = _make_paths(td)
            # Pre-existing backup with custom marker
            backup_target = meta_path.with_name(
                meta_path.stem + ".legacy" + meta_path.suffix
            )
            backup_target.write_text('{"custom": "preserved"}')

            migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            # Backup file content unchanged
            self.assertEqual(
                backup_target.read_text(), '{"custom": "preserved"}',
            )


class TestMigrateMetaIdempotent(unittest.TestCase):
    def test_rerun_skips_already_migrated(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            paths = _make_paths(td)
            # First run migrates everything
            r1 = migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            self.assertEqual(len(r1["migrated"]), 2)
            # Second run: nothing to migrate
            r2 = migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            self.assertEqual(r2["migrated"], [])
            self.assertEqual(set(r2["skipped"]), {"alpha", "beta"})
            self.assertIsNone(r2["backup_path"])

    def test_mixed_migrated_and_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            # Pre-migrate alpha by hand
            data = json.loads(meta_path.read_text())
            data["projects"]["alpha"]["capabilities_schema_version"] = (
                CAPABILITY_SCHEMA_VERSION
            )
            data["projects"]["alpha"]["capabilities"] = {
                "code_repo": {"state": "provisioned"},
            }
            meta_path.write_text(json.dumps(data))

            paths = _make_paths(td)
            r = migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            self.assertEqual(r["migrated"], ["beta"])
            self.assertEqual(r["skipped"], ["alpha"])

    def test_meta_missing_returns_empty_result(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = Path(td) / "ghost.json"
            r = migrate_meta(
                meta_path, dry_run=True,
                paths=_make_paths(td),
                skip_remote=True, skip_systemctl=True,
            )
            self.assertEqual(r["migrated"], [])
            self.assertEqual(r["skipped"], [])


class TestMigrateMetaSkipKnowledge(unittest.TestCase):
    """W1 review fix #2: skip_knowledge propagates through migrate_meta."""

    def test_skip_knowledge_produces_skipped_state(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            paths = _make_paths(td)
            r = migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
                skip_knowledge=True,
            )
            self.assertEqual(set(r["migrated"]), {"alpha", "beta"})
            data = json.loads(meta_path.read_text())
            for slug in ("alpha", "beta"):
                ks = data["projects"][slug]["capabilities"]["knowledge_slot"]
                self.assertEqual(ks["state"], "skipped")
                self.assertIn("drift_reason", ks)


class TestLegacyDetection(unittest.TestCase):
    def test_pre_migration_meta_is_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            data = json.loads(meta_path.read_text())
            self.assertTrue(is_legacy_meta(data))
            self.assertTrue(is_legacy_entry(data["projects"]["alpha"]))

    def test_post_migration_meta_not_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            meta_path = _seed_legacy_meta(td)
            paths = _make_paths(td)
            migrate_meta(
                meta_path, dry_run=False, paths=paths,
                skip_remote=True, skip_systemctl=True,
            )
            data = json.loads(meta_path.read_text())
            self.assertFalse(is_legacy_meta(data))


if __name__ == "__main__":
    unittest.main()
