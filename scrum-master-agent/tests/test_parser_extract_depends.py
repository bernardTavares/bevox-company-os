"""Testes parser.extract_depends (wave-6 scrum-master-v2)."""
import unittest

from lib import parser


class TestExtractDepends(unittest.TestCase):
    def test_no_depends_line_returns_empty(self):
        body = "### Task 2.1: X\n\n**Files:**\n- Create: `a.py`\n\n- [ ] Step 1"
        self.assertEqual(parser.extract_depends(body), [])

    def test_single_dep(self):
        body = "**Depends:** Task 1.1"
        self.assertEqual(parser.extract_depends(body), ["Task 1.1"])

    def test_comma_separated_deps(self):
        body = "**Depends:** Task 1.1, Task 2.3, Task 3.2"
        self.assertEqual(parser.extract_depends(body),
                         ["Task 1.1", "Task 2.3", "Task 3.2"])

    def test_phase_suffix_stripped(self):
        """Cross-phase normalization: strip parenthetical suffixes."""
        body = "**Depends:** Task 1.1 (Phase 1), Task 2.3 (Phase 2)"
        result = parser.extract_depends(body)
        self.assertEqual(result, ["Task 1.1", "Task 2.3"])

    def test_extra_whitespace_normalized(self):
        body = "**Depends:**   Task 1.1  ,   Task 2.1  "
        self.assertEqual(parser.extract_depends(body),
                         ["Task 1.1", "Task 2.1"])

    def test_empty_after_colon_returns_empty(self):
        body = "**Depends:** "
        self.assertEqual(parser.extract_depends(body), [])


if __name__ == "__main__":
    unittest.main()
