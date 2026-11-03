"""Tests materializer resolve sprint_target per-project (schema v4)."""
import unittest
from unittest.mock import patch, MagicMock


class TestMaterializerPerProjectSprint(unittest.TestCase):
    def test_materialize_resolves_sprint_target_per_project(self):
        """proposal de bevox-mobile com sprint_target=current vai pra current de bevox-mobile."""
        from lib import materializer

        state = {
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-7", "state": "current", "project": "bevox-mobile"},
                {"id": "sprint-8", "state": "next", "project": "bevox-mobile"},
                {"id": "sprint-9", "state": "current", "project": "bevox-backend"},
            ],
            "tasks": [],
        }
        sid = materializer._resolve_target_sprint(state, "current", "bevox-mobile")
        self.assertEqual(sid, "sprint-7")
        sid2 = materializer._resolve_target_sprint(state, "current", "bevox-backend")
        self.assertEqual(sid2, "sprint-9")

    def test_materialize_fails_no_sprint_for_project(self):
        from lib import materializer
        state = {
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-7", "state": "current", "project": "bevox-mobile"},
            ],
            "tasks": [],
        }
        with self.assertRaises(ValueError) as ctx:
            materializer._resolve_target_sprint(state, "current", "bevox-backend")
        self.assertIn("NO_SPRINT_FOR_PROJECT", str(ctx.exception))

    def test_materialize_target_next_works_per_project(self):
        from lib import materializer
        state = {
            "schema_version": 4,
            "sprints": [
                {"id": "sprint-7", "state": "current", "project": "bevox-mobile"},
                {"id": "sprint-8", "state": "next", "project": "bevox-mobile"},
            ],
            "tasks": [],
        }
        sid = materializer._resolve_target_sprint(state, "next", "bevox-mobile")
        self.assertEqual(sid, "sprint-8")


if __name__ == "__main__":
    unittest.main()
