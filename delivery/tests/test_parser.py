"""Tests for spec parser, normalize, compute_key."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent

FIXTURE = Path(__file__).parent / "fixtures" / "spec-sample.md"


class TestNormalize(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(agent.normalize_text("Hello World"), "hello world")

    def test_collapse_whitespace(self):
        self.assertEqual(agent.normalize_text("foo   bar\tbaz"), "foo bar baz")

    def test_strip_leading_markdown(self):
        self.assertEqual(agent.normalize_text("- foo bar"), "foo bar")
        self.assertEqual(agent.normalize_text("* foo bar"), "foo bar")
        self.assertEqual(agent.normalize_text("- [ ] foo bar"), "foo bar")
        self.assertEqual(agent.normalize_text("- [x] foo bar"), "foo bar")

    def test_idempotent(self):
        s = "- [ ] Some Task TEXT"
        once = agent.normalize_text(s)
        twice = agent.normalize_text(once)
        self.assertEqual(once, twice)


class TestComputeKey(unittest.TestCase):
    def test_returns_16_hex_chars(self):
        k = agent.compute_key("x.md", "Tarefas", "do thing")
        self.assertEqual(len(k), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in k))

    def test_stable_across_whitespace(self):
        k1 = agent.compute_key("x.md", "Tarefas", "do  thing")
        k2 = agent.compute_key("x.md", "Tarefas", "do thing")
        self.assertEqual(k1, k2)

    def test_stable_across_case(self):
        k1 = agent.compute_key("x.md", "Tarefas", "Do Thing")
        k2 = agent.compute_key("x.md", "Tarefas", "do thing")
        self.assertEqual(k1, k2)

    def test_stable_across_bullet_prefix(self):
        k1 = agent.compute_key("x.md", "Tarefas", "- do thing")
        k2 = agent.compute_key("x.md", "Tarefas", "do thing")
        self.assertEqual(k1, k2)

    def test_changes_with_spec_path(self):
        k1 = agent.compute_key("a.md", "Tarefas", "do thing")
        k2 = agent.compute_key("b.md", "Tarefas", "do thing")
        self.assertNotEqual(k1, k2)

    def test_changes_with_section(self):
        k1 = agent.compute_key("x.md", "Tarefas", "do thing")
        k2 = agent.compute_key("x.md", "Plan", "do thing")
        self.assertNotEqual(k1, k2)


class TestParseSpec(unittest.TestCase):
    def test_extracts_tarefas_section(self):
        items = agent.parse_spec(FIXTURE)
        # Should pick up items under "Tarefas", "Plan" and "Tasks"
        # but NOT under "Contexto" or "Outras notas"
        texts = [i["item_text"] for i in items]
        self.assertIn("Implementar funcao foo", texts)
        self.assertIn("Adicionar validacao de bar", texts)
        self.assertIn("Escrever teste para baz", texts)

    def test_extracts_plan_section(self):
        items = agent.parse_spec(FIXTURE)
        texts = [i["item_text"] for i in items]
        self.assertIn("Item with checkbox A", texts)
        self.assertIn("Item with checkbox B", texts)

    def test_extracts_tasks_section(self):
        items = agent.parse_spec(FIXTURE)
        texts = [i["item_text"] for i in items]
        self.assertIn("Task in english", texts)

    def test_skips_contexto_section(self):
        items = agent.parse_spec(FIXTURE)
        texts = [i["item_text"] for i in items]
        self.assertNotIn("Some context paragraph that should NOT be parsed as tasks.", texts)

    def test_skips_notes_section(self):
        items = agent.parse_spec(FIXTURE)
        texts = [i["item_text"] for i in items]
        self.assertNotIn("Texto livre, nao parseavel como task.", texts)

    def test_section_id_attached(self):
        items = agent.parse_spec(FIXTURE)
        # Each item should know which section it came from
        sections = {i["section_id"] for i in items}
        self.assertIn("Tarefas", sections)
        self.assertIn("Plan", sections)
        self.assertIn("Tasks", sections)

    def test_missing_file_returns_empty(self):
        items = agent.parse_spec(Path("/tmp/does-not-exist-xyz.md"))
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
