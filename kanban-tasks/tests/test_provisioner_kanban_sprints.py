"""Unit tests for lib.provisioners.kanban_sprints.provision_kanban_sprints."""
import unittest
from unittest.mock import patch

from lib.provisioners.kanban_sprints import provision_kanban_sprints


class TestProvisionKanbanSprints(unittest.TestCase):
    def test_happy_path(self):
        with patch(
            "lib.project_factory.step_2_kanban_bootstrap"
        ) as mock_step:
            mock_step.return_value = {"sprints_created": 2}
            res = provision_kanban_sprints("alpha")
        self.assertEqual(res.state, "provisioned")
        self.assertEqual(res.sprints_created, 2)

    def test_failure_returns_absent(self):
        with patch(
            "lib.project_factory.step_2_kanban_bootstrap",
            side_effect=RuntimeError("boom"),
        ):
            res = provision_kanban_sprints("alpha")
        self.assertEqual(res.state, "absent")
        self.assertIn("boom", res.error or "")


if __name__ == "__main__":
    unittest.main()
