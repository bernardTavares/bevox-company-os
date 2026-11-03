"""Smoke tests for the canonical allowlist module."""
import unittest

from lib import allowlist


class TestAllowlist(unittest.TestCase):
    def setUp(self):
        self.tools = allowlist.default_tools()

    def test_returns_string(self):
        self.assertIsInstance(self.tools, str)
        self.assertGreater(len(self.tools), 0)

    def test_contains_core_baseline(self):
        for required in ("Read", "Write", "Edit", "Glob", "Grep",
                         "Bash(git:*)", "Bash(rm:*)", "Bash(python3:*)",
                         "Bash(pytest:*)"):
            self.assertIn(required, self.tools)

    def test_contains_node_toolchain(self):
        for required in ("Bash(pnpm:*)", "Bash(node:*)", "Bash(npx:*)",
                         "Bash(tsc:*)", "Bash(eslint:*)", "Bash(prettier:*)"):
            self.assertIn(required, self.tools)

    def test_contains_python_extras(self):
        for required in ("Bash(pip:*)", "Bash(ruff:*)", "Bash(mypy:*)",
                         "Bash(black:*)"):
            self.assertIn(required, self.tools)

    def test_contains_safe_docker_subset(self):
        for required in ("Bash(docker build:*)", "Bash(docker images:*)",
                         "Bash(docker rmi:*)", "Bash(docker inspect:*)"):
            self.assertIn(required, self.tools)

    def test_excludes_dangerous_docker(self):
        for forbidden in ("docker run", "docker exec", "docker volume",
                          "docker network", "docker --privileged",
                          "docker save", "docker load", "docker cp"):
            self.assertNotIn(forbidden, self.tools)

    def test_excludes_egress_and_cloud(self):
        for forbidden in ("Bash(curl:", "Bash(wget:", "Bash(ssh:",
                          "Bash(scp:", "Bash(rsync:", "Bash(gh:",
                          "Bash(systemctl:", "Bash(kubectl:",
                          "Bash(aws:", "Bash(gcloud:", "Bash(terraform:"):
            self.assertNotIn(forbidden, self.tools)

    def test_excludes_arbitrary_path_exec(self):
        # Wildcard exec patterns devem estar fora.
        self.assertNotIn("Bash(./", self.tools)
        # Internal CLI específico continua permitido (clarification-agent),
        # mas exec genérico em /tmp/, /usr/local/, etc. NÃO.
        self.assertNotIn("Bash(/tmp/", self.tools)
        self.assertNotIn("Bash(/usr/", self.tools)

    def test_contains_file_helpers(self):
        for required in ("Bash(find:*)", "Bash(jq:*)", "Bash(diff:*)",
                         "Bash(head:*)", "Bash(tail:*)", "Bash(grep:*)"):
            self.assertIn(required, self.tools)


if __name__ == "__main__":
    unittest.main()
