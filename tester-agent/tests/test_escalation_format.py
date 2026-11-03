"""Tests for tester escalation file frontmatter (UBN pre-req).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §3.2
"""
import unittest
import tempfile
from pathlib import Path
from lib import store


class TestReadEscalation(unittest.TestCase):
    def test_returns_none_for_legacy_format_without_frontmatter(self):
        """Legacy escalation files (sem frontmatter) retornam None."""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write("# Tester escalation — T-0001-tr-1\n\n**Task:** T-0001\n")
            path = Path(f.name)
        try:
            result = store.read_escalation(path)
            self.assertIsNone(result)
        finally:
            path.unlink()

    def test_parses_frontmatter_v1(self):
        """Files com frontmatter retornam dict com campos canônicos."""
        content = """---
test_run_id: T-0042-tr-3
task_id: T-0042
decision: proposed_rejected
structural_concern: spec_inconsistent
generated_at: 2026-04-30T12:00:00Z
---

# Tester escalation — T-0042-tr-3
"""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            result = store.read_escalation(path)
            self.assertIsNotNone(result)
            self.assertEqual(result["test_run_id"], "T-0042-tr-3")
            self.assertEqual(result["task_id"], "T-0042")
            self.assertEqual(result["decision"], "proposed_rejected")
            self.assertEqual(result["structural_concern"], "spec_inconsistent")
        finally:
            path.unlink()

    def test_returns_none_for_missing_required_field(self):
        """Frontmatter sem decision retorna None (defensivo)."""
        content = """---
task_id: T-0001
---
"""
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            path = Path(f.name)
        try:
            result = store.read_escalation(path)
            self.assertIsNone(result)
        finally:
            path.unlink()


class TestWriteEscalationFrontmatter(unittest.TestCase):
    def test_write_then_read_roundtrip(self):
        """Files escritos por _write_escalation_md são parseáveis por read_escalation."""
        from lib import lifecycle
        from unittest.mock import patch
        import shutil

        tmp = tempfile.mkdtemp()
        try:
            with patch.object(store, "ESCALATIONS_DIR", Path(tmp)):
                checks = [{
                    "ac": "test AC",
                    "effective_structural_concern": "spec_inconsistent",
                    "evidence": "evidência",
                    "valid_sources": ["/tmp/x"],
                    "sources": [],
                }]
                lifecycle._write_escalation_md("T-0099-tr-2", "T-0099", checks)
            files = list(Path(tmp).glob("*.md"))
            self.assertEqual(len(files), 1)
            data = store.read_escalation(files[0])
            self.assertIsNotNone(data, "frontmatter ausente — escalation não parseável")
            self.assertEqual(data["task_id"], "T-0099")
            self.assertEqual(data["test_run_id"], "T-0099-tr-2")
            self.assertEqual(data["decision"], "proposed_rejected")
            self.assertEqual(data["structural_concern"], "spec_inconsistent")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_write_escalation_no_structural_concerns(self):
        """When checks lack effective_structural_concern, suggested defaults to 'manual'."""
        from lib import lifecycle
        from unittest.mock import patch
        import shutil

        tmp = tempfile.mkdtemp()
        try:
            with patch.object(store, "ESCALATIONS_DIR", Path(tmp)):
                checks = [{
                    "ac": "AC sem structural concern",
                    "effective_structural_concern": "",  # vazio = falsy
                    "evidence": "",
                    "valid_sources": [],
                    "sources": [],
                }]
                lifecycle._write_escalation_md("T-edge-tr-1", "T-edge", checks)
            files = list(Path(tmp).glob("*.md"))
            self.assertEqual(len(files), 1)
            data = store.read_escalation(files[0])
            self.assertIsNotNone(data)
            self.assertEqual(data["structural_concern"], "manual")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
